#!/usr/bin/env python3
"""
Unified sync script for WordPress → MySQL → Go High Level.
Runs every 10 minutes and only syncs leads from the last 10 minutes.
Production-ready for Ubuntu deployment.
"""

import os
import sys
import logging
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
import pymysql
from dotenv import load_dotenv
import requests
import base64
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.wordpress_leads_extractor.api.ghl_client import GHLClient
from sync_to_mysql import LeadCleaner

# Load environment variables
load_dotenv()

# Configure logging for production
LOG_DIR = Path("/var/log/wordpress-leads-sync")
if not LOG_DIR.exists() and os.geteuid() == 0:  # Running as root
    LOG_DIR.mkdir(parents=True, exist_ok=True)
elif not LOG_DIR.exists():
    LOG_DIR = Path("logs")
    LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'unified_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested = True


class UnifiedSyncService:
    """Unified service for complete lead sync pipeline."""
    
    def __init__(self):
        """Initialize all connections and configurations."""
        # WordPress configuration
        self.wp_url = os.getenv('WORDPRESS_URL')
        self.wp_username = os.getenv('WORDPRESS_USERNAME')
        self.wp_password = os.getenv('WORDPRESS_PASSWORD')
        
        # MySQL configuration
        self.db_config = {
            'host': os.getenv('MYSQL_HOST'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        
        # Add SSL for DigitalOcean
        if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
            self.db_config['ssl'] = {'ssl_disabled': False}
        
        # GHL configuration
        self.ghl_client = GHLClient(
            access_token=os.getenv('GHL_ACCESS_TOKEN'),
            location_id=os.getenv('GHL_LOCATION_ID')
        )
        
        # Lead cleaner
        self.cleaner = LeadCleaner()
        
        # Sync interval (minutes)
        self.sync_interval = int(os.getenv('SYNC_INTERVAL_MINUTES', 10))
        
    def get_db_connection(self):
        """Get MySQL database connection."""
        return pymysql.connect(**self.db_config)
    
    def fetch_wordpress_leads(self, since_datetime: datetime) -> list:
        """
        Fetch leads from WordPress since a specific datetime.
        
        Args:
            since_datetime: Only fetch leads created after this time
            
        Returns:
            List of lead dictionaries
        """
        try:
            # Format datetime for API
            since_str = since_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
            # Prepare auth headers
            credentials = base64.b64encode(
                f"{self.wp_username}:{self.wp_password}".encode()
            ).decode()
            headers = {"Authorization": f"Basic {credentials}"}
            
            # Fetch leads with time filter
            params = {
                'since': since_str,
                'limit': 1000  # Max per request
            }
            
            response = requests.get(
                f"{self.wp_url}/wp-json/rolling-riches/v1/leads",
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            leads = data.get('leads', [])
            
            logger.info(f"Fetched {len(leads)} leads from WordPress since {since_str}")
            return leads
            
        except Exception as e:
            logger.error(f"Failed to fetch WordPress leads: {e}")
            return []
    
    def process_lead(self, lead: dict) -> dict:
        """Process and clean a lead."""
        processed = {}
        raw_data = lead.get('raw_data', lead)
        
        # Clean email
        email, email_valid = self.cleaner.clean_email(raw_data.get('email', ''))
        processed['email'] = email
        processed['email_valid'] = email_valid
        
        # Extract email domain
        if email and '@' in email:
            processed['email_domain'] = email.split('@')[1]
        else:
            processed['email_domain'] = None
        
        # Clean phone
        phone_cleaned, phone_country, phone_valid = self.cleaner.clean_phone(
            raw_data.get('phone', '')
        )
        processed['phone'] = raw_data.get('phone', '')
        processed['phone_country'] = phone_country
        processed['phone_valid'] = phone_valid
        processed['phone_type'] = 'mobile' if phone_valid else None
        
        # Names
        processed['first_name'] = raw_data.get('first_name', '')
        processed['last_name'] = raw_data.get('last_name', '')
        
        # Process dates
        signup_date_str = raw_data.get('signup_date', '')
        if signup_date_str:
            try:
                signup_dt = datetime.strptime(signup_date_str, '%Y-%m-%d %H:%M:%S')
                processed['signup_date'] = signup_dt.date()
                processed['signup_datetime'] = signup_dt
            except:
                processed['signup_date'] = datetime.now().date()
                processed['signup_datetime'] = datetime.now()
        else:
            processed['signup_date'] = datetime.now().date()
            processed['signup_datetime'] = datetime.now()
        
        # Other fields
        processed['source'] = 'wordpress'
        processed['source_id'] = str(raw_data.get('id', ''))
        
        # Calculate quality score
        processed['quality_score'] = self.cleaner.calculate_quality_score(processed)
        
        return processed
    
    def save_lead_to_mysql(self, lead: dict) -> tuple:
        """
        Save lead to MySQL database.
        
        Returns:
            (success, is_new, lead_id)
        """
        processed = self.process_lead(lead)
        
        if not processed['email']:
            logger.warning(f"Skipping lead with no email")
            return False, False, None
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check if exists
                cursor.execute(
                    "SELECT id FROM leads WHERE email = %s LIMIT 1",
                    (processed['email'],)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update last seen
                    cursor.execute(
                        "UPDATE leads SET updated_at = NOW() WHERE id = %s",
                        (existing[0],)
                    )
                    conn.commit()
                    return True, False, existing[0]
                else:
                    # Insert new lead
                    cursor.execute("""
                        INSERT INTO leads (
                            email, phone, first_name, last_name,
                            signup_date, signup_datetime, source, source_id,
                            phone_country, phone_type, phone_valid,
                            email_valid, email_domain, quality_score
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        processed['email'],
                        processed.get('phone'),
                        processed.get('first_name'),
                        processed.get('last_name'),
                        processed.get('signup_date'),
                        processed.get('signup_datetime'),
                        processed.get('source', 'wordpress'),
                        processed.get('source_id'),
                        processed.get('phone_country'),
                        processed.get('phone_type'),
                        processed.get('phone_valid', False),
                        processed.get('email_valid', False),
                        processed.get('email_domain'),
                        processed.get('quality_score', 0)
                    ))
                    conn.commit()
                    return True, True, cursor.lastrowid
                    
        except pymysql.IntegrityError as e:
            if 'Duplicate entry' in str(e):
                logger.debug(f"Duplicate lead: {processed['email']}")
                return True, False, None
            else:
                logger.error(f"Database error: {e}")
                return False, False, None
        except Exception as e:
            logger.error(f"Error saving lead: {e}")
            return False, False, None
        finally:
            conn.close()
    
    def sync_lead_to_ghl(self, lead_id: int) -> bool:
        """
        Sync a lead from MySQL to Go High Level.
        
        Args:
            lead_id: Database ID of the lead
            
        Returns:
            True if successful
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Get lead data
                cursor.execute(
                    "SELECT * FROM leads WHERE id = %s AND ghl_synced = FALSE",
                    (lead_id,)
                )
                lead = cursor.fetchone()
                
                if not lead:
                    return False
                
                # Prepare tags
                tags = ["wordpress-lead", "auto-sync"]
                if lead['quality_score'] >= 80:
                    tags.append("high-quality")
                elif lead['quality_score'] >= 50:
                    tags.append("medium-quality")
                else:
                    tags.append("low-quality")
                
                if lead['signup_date']:
                    tags.append(f"signup-{lead['signup_date'].strftime('%Y-%m')}")
                
                # Custom fields
                custom_fields = {
                    "signup_date": lead['signup_datetime'].isoformat() if lead['signup_datetime'] else None,
                    "quality_score": str(lead['quality_score']),
                    "source": "WordPress Sweepstakes"
                }
                
                # Create/update in GHL
                result = self.ghl_client.create_or_update_contact(
                    email=lead['email'],
                    phone=lead.get('phone'),
                    first_name=lead.get('first_name'),
                    last_name=lead.get('last_name'),
                    tags=tags,
                    custom_fields=custom_fields,
                    source="WordPress Lead Form"
                )
                
                # Log the sync attempt
                cursor.execute("""
                    INSERT INTO ghl_sync_log (
                        lead_id, email, request_timestamp, request_body,
                        response_status_code, response_body, response_timestamp,
                        status, error_message, ghl_contact_id, ghl_location_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    lead_id,
                    lead['email'],
                    result.get('request_timestamp'),
                    json.dumps(result.get('request_body')),
                    result.get('response_status_code'),
                    json.dumps(result.get('response_body')),
                    result.get('response_timestamp'),
                    'success' if result.get('success') else 'failed',
                    result.get('error_message'),
                    result.get('ghl_contact_id'),
                    self.ghl_client.location_id
                ))
                
                # Update lead if successful
                if result.get('success') and result.get('ghl_contact_id'):
                    cursor.execute("""
                        UPDATE leads SET
                            ghl_synced = TRUE,
                            ghl_synced_at = NOW(),
                            ghl_contact_id = %s
                        WHERE id = %s
                    """, (result.get('ghl_contact_id'), lead_id))
                    
                    conn.commit()
                    logger.info(f"Successfully synced lead {lead['email']} to GHL")
                    return True
                else:
                    conn.commit()
                    logger.warning(f"Failed to sync lead {lead['email']}: {result.get('error_message')}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error syncing lead {lead_id} to GHL: {e}")
            return False
        finally:
            conn.close()
    
    def run_sync_cycle(self):
        """Run a complete sync cycle."""
        start_time = datetime.now()
        
        # Calculate time window (last N minutes + 1 minute buffer)
        since_datetime = start_time - timedelta(minutes=self.sync_interval + 1)
        
        logger.info(f"Starting sync cycle at {start_time}")
        logger.info(f"Fetching leads since {since_datetime}")
        
        stats = {
            'wp_fetched': 0,
            'mysql_new': 0,
            'mysql_updated': 0,
            'ghl_synced': 0,
            'ghl_failed': 0,
            'errors': 0
        }
        
        try:
            # Step 1: Fetch from WordPress
            wp_leads = self.fetch_wordpress_leads(since_datetime)
            stats['wp_fetched'] = len(wp_leads)
            
            # Step 2: Save to MySQL
            new_lead_ids = []
            for lead in wp_leads:
                try:
                    success, is_new, lead_id = self.save_lead_to_mysql(lead)
                    if success:
                        if is_new:
                            stats['mysql_new'] += 1
                            if lead_id:
                                new_lead_ids.append(lead_id)
                        else:
                            stats['mysql_updated'] += 1
                except Exception as e:
                    logger.error(f"Error processing lead: {e}")
                    stats['errors'] += 1
            
            # Step 3: Sync new leads to GHL
            for lead_id in new_lead_ids:
                try:
                    if self.sync_lead_to_ghl(lead_id):
                        stats['ghl_synced'] += 1
                    else:
                        stats['ghl_failed'] += 1
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error syncing lead {lead_id} to GHL: {e}")
                    stats['ghl_failed'] += 1
            
            # Log cycle summary
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Sync cycle completed in {duration:.1f} seconds")
            logger.info(f"Stats: {stats}")
            
            # Log to sync_log table
            self.log_sync_cycle(stats, duration)
            
        except Exception as e:
            logger.error(f"Sync cycle failed: {e}")
            stats['errors'] += 1
    
    def log_sync_cycle(self, stats: dict, duration: float):
        """Log sync cycle to database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sync_log (
                        sync_type, sync_completed_at, total_records,
                        new_records, updated_records, failed_records,
                        status, duration_seconds
                    ) VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
                """, (
                    'unified_sync',
                    stats['wp_fetched'],
                    stats['mysql_new'],
                    stats['mysql_updated'],
                    stats['ghl_failed'],
                    'completed',
                    int(duration)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log sync cycle: {e}")
        finally:
            conn.close()
    
    def run_continuous(self):
        """Run continuous sync with specified interval."""
        logger.info(f"Starting continuous sync (interval: {self.sync_interval} minutes)")
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        while not shutdown_requested:
            try:
                # Run sync cycle
                self.run_sync_cycle()
                
                # Wait for next cycle
                if not shutdown_requested:
                    logger.info(f"Waiting {self.sync_interval} minutes until next sync...")
                    for _ in range(self.sync_interval * 60):
                        if shutdown_requested:
                            break
                        time.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error in continuous sync: {e}")
                if not shutdown_requested:
                    logger.info("Waiting 1 minute before retry...")
                    time.sleep(60)
        
        logger.info("Continuous sync stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified WordPress → MySQL → GHL sync")
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=10, help='Sync interval in minutes')
    parser.add_argument('--test', action='store_true', help='Test connections')
    
    args = parser.parse_args()
    
    # Check required environment variables
    required_vars = [
        'WORDPRESS_URL', 'WORDPRESS_USERNAME', 'WORDPRESS_PASSWORD',
        'MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE',
        'GHL_ACCESS_TOKEN', 'GHL_LOCATION_ID'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Set sync interval
    if args.interval:
        os.environ['SYNC_INTERVAL_MINUTES'] = str(args.interval)
    
    # Initialize service
    service = UnifiedSyncService()
    
    if args.test:
        logger.info("Testing connections...")
        
        # Test MySQL
        try:
            conn = service.get_db_connection()
            logger.info("[OK] MySQL connection successful")
            conn.close()
        except Exception as e:
            logger.error(f"[FAIL] MySQL connection failed: {e}")
        
        # Test WordPress
        try:
            leads = service.fetch_wordpress_leads(datetime.now() - timedelta(days=1))
            logger.info(f"[OK] WordPress API working ({len(leads)} leads found)")
        except Exception as e:
            logger.error(f"[FAIL] WordPress API failed: {e}")
        
        # Test GHL
        try:
            if service.ghl_client.test_connection():
                logger.info("[OK] Go High Level connection successful")
            else:
                logger.error("[FAIL] Go High Level connection failed")
        except Exception as e:
            logger.error(f"[FAIL] Go High Level error: {e}")
            
    elif args.continuous or not args.once:
        # Default to continuous mode
        service.run_continuous()
    else:
        # Run once
        service.run_sync_cycle()


if __name__ == "__main__":
    main()