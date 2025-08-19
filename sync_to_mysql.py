#!/usr/bin/env python3
"""
Production-ready WordPress to MySQL lead sync script.
Fetches leads from WordPress and syncs to MySQL with cleaning and deduplication.
"""

import os
import sys
import logging
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import base64
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import phonenumbers
from email_validator import validate_email, EmailNotValidError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('leads_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LeadCleaner:
    """Cleans and validates lead data."""
    
    @staticmethod
    def clean_email(email: str) -> Tuple[str, bool]:
        """Clean and validate email address."""
        if not email:
            return '', False
            
        email = email.strip().lower()
        
        try:
            # Validate email
            validation = validate_email(email)
            return validation.email, True
        except EmailNotValidError:
            return email, False
    
    @staticmethod
    def clean_phone(phone: str, default_country: str = 'US') -> Tuple[str, str, bool]:
        """
        Clean and validate phone number.
        Returns: (cleaned_number, country_code, is_valid)
        """
        if not phone:
            return '', '', False
            
        phone = phone.strip()
        
        try:
            # Parse phone number
            parsed = phonenumbers.parse(phone, default_country)
            
            if phonenumbers.is_valid_number(parsed):
                # Format as international
                cleaned = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                country = phonenumbers.region_code_for_number(parsed)
                return cleaned, country, True
            else:
                # Remove non-digits for storage even if invalid
                digits_only = re.sub(r'[^\d]', '', phone)
                return digits_only, '', False
                
        except phonenumbers.NumberParseException:
            # Just clean it
            digits_only = re.sub(r'[^\d]', '', phone)
            return digits_only, '', False
    
    @staticmethod
    def calculate_quality_score(lead: Dict) -> int:
        """Calculate lead quality score (0-100)."""
        score = 50  # Base score
        
        # Valid email (+20)
        if lead.get('email_valid'):
            score += 20
        
        # Has phone (+15)
        if lead.get('phone_cleaned') and len(lead.get('phone_cleaned', '')) >= 10:
            score += 15
        
        # Valid phone (+10)
        if lead.get('phone_valid'):
            score += 10
        
        # Not a free email provider (+10)
        email_domain = lead.get('email', '').split('@')[-1].lower()
        if email_domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
            score += 10
        
        # Has good source (-5 for test/unknown)
        if lead.get('source', '').lower() in ['test', 'unknown', '']:
            score -= 5
            
        return min(max(score, 0), 100)


class WordPressSync:
    """Handles WordPress API interactions."""
    
    def __init__(self, site_url: str, username: str, password: str):
        self.site_url = site_url.rstrip('/')
        self.username = username
        self.password = password
        
        # Setup authentication
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode('ascii')
        self.headers = {'Authorization': f'Basic {credentials}'}
    
    def fetch_leads(self, since: Optional[datetime] = None, 
                    last_id: Optional[int] = None,
                    limit: int = 100) -> List[Dict]:
        """Fetch leads from WordPress API."""
        params = {'limit': limit}
        
        if since:
            params['since'] = since.strftime('%Y-%m-%d %H:%M:%S')
        
        if last_id:
            params['last_id'] = last_id
            
        try:
            response = requests.get(
                f"{self.site_url}/wp-json/rolling-riches/v1/leads",
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('leads', [])
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch leads from WordPress: {e}")
            raise


class MySQLSync:
    """Handles MySQL database operations."""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.connection_params = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database,
            'charset': 'utf8mb4',
            'cursorclass': DictCursor
        }
        # Add SSL support for DigitalOcean
        if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
            self.connection_params['ssl'] = {'ssl_disabled': False}
        self.cleaner = LeadCleaner()
    
    def get_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.connection_params)
    
    def get_last_sync_info(self) -> Tuple[Optional[datetime], Optional[int]]:
        """Get last sync date and last ID from database."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Get last successful sync
                cursor.execute("""
                    SELECT MAX(l.signup_date) as last_signup_date, MAX(l.source_id) as last_wp_id
                    FROM leads l
                    WHERE l.source = 'wordpress'
                """)
                result = cursor.fetchone()
                
                if result:
                    return result.get('last_signup_date'), result.get('last_wp_id')
                    
                return None, None
    
    def start_sync_log(self) -> int:
        """Create sync log entry and return its ID."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sync_log (sync_type, sync_started_at, status)
                    VALUES ('wordpress_to_mysql', NOW(), 'running')
                """)
                conn.commit()
                return cursor.lastrowid
    
    def update_sync_log(self, sync_id: int, **kwargs):
        """Update sync log entry."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                updates = []
                values = []
                
                for key, value in kwargs.items():
                    updates.append(f"{key} = %s")
                    values.append(value)
                
                values.append(sync_id)
                
                cursor.execute(f"""
                    UPDATE sync_log 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, values)
                conn.commit()
    
    def process_lead(self, lead: Dict) -> Dict:
        """Clean and process a lead."""
        processed = {}
        
        # Extract raw data
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
                signup_dt = datetime.strptime(
                    signup_date_str, '%Y-%m-%d %H:%M:%S'
                )
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
    
    def save_lead(self, lead: Dict) -> Tuple[bool, bool]:
        """
        Save lead to database.
        Returns: (success, is_new)
        """
        processed = self.process_lead(lead)
        
        if not processed['email']:
            logger.warning(f"Skipping lead with no email: {lead}")
            return False, False
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # Check if exists
                    cursor.execute("""
                        SELECT id FROM leads 
                        WHERE email = %s
                        LIMIT 1
                    """, (processed['email'],))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update last synced
                        cursor.execute("""
                            UPDATE leads 
                            SET updated_at = NOW()
                            WHERE id = %s
                        """, (existing['id'],))
                        conn.commit()
                        return True, False
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
                        return True, True
                        
                except pymysql.IntegrityError as e:
                    if 'Duplicate entry' in str(e):
                        return True, False
                    logger.error(f"Database error saving lead: {e}")
                    return False, False
                except Exception as e:
                    logger.error(f"Error saving lead: {e}")
                    return False, False


class LeadSyncService:
    """Main service for syncing leads."""
    
    def __init__(self):
        # WordPress config
        self.wp_sync = WordPressSync(
            site_url=os.getenv('WORDPRESS_URL'),
            username=os.getenv('WORDPRESS_USERNAME'),
            password=os.getenv('WORDPRESS_PASSWORD')
        )
        
        # MySQL config
        self.mysql_sync = MySQLSync(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE', 'rolling_riches_leads')
        )
    
    def run_sync(self, full_sync: bool = False):
        """Run the sync process."""
        sync_id = self.mysql_sync.start_sync_log()
        
        try:
            logger.info("Starting lead sync...")
            
            # Get last sync info
            if not full_sync:
                last_date, last_id = self.mysql_sync.get_last_sync_info()
            else:
                last_date, last_id = None, None
                
            logger.info(f"Last sync: date={last_date}, id={last_id}")
            
            # Fetch leads from WordPress
            leads = self.wp_sync.fetch_leads(
                since=last_date,
                last_id=last_id,
                limit=500
            )
            
            logger.info(f"Fetched {len(leads)} leads from WordPress")
            
            # Process leads
            stats = {
                'fetched': len(leads),
                'inserted': 0,
                'updated': 0,
                'skipped': 0,
                'errors': 0
            }
            
            last_signup_date = None
            
            for lead in leads:
                try:
                    success, is_new = self.mysql_sync.save_lead(lead)
                    
                    if success:
                        if is_new:
                            stats['inserted'] += 1
                        else:
                            stats['updated'] += 1
                    else:
                        stats['skipped'] += 1
                        
                    # Track last signup date
                    if lead.get('raw_data', {}).get('signup_date'):
                        try:
                            lead_date = datetime.strptime(
                                lead['raw_data']['signup_date'], 
                                '%Y-%m-%d %H:%M:%S'
                            )
                            if not last_signup_date or lead_date > last_signup_date:
                                last_signup_date = lead_date
                        except:
                            pass
                            
                except Exception as e:
                    logger.error(f"Error processing lead: {e}")
                    stats['errors'] += 1
            
            # Update sync log
            self.mysql_sync.update_sync_log(
                sync_id,
                sync_completed_at=datetime.now(),
                total_records=stats['fetched'],
                new_records=stats['inserted'],
                updated_records=stats['updated'],
                failed_records=stats['errors'],
                duplicate_records=stats['updated'],
                status='completed'
            )
            
            logger.info(f"Sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.mysql_sync.update_sync_log(
                sync_id,
                sync_completed_at=datetime.now(),
                status='failed',
                error_message=str(e)
            )
            raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync WordPress leads to MySQL')
    parser.add_argument('--full', action='store_true', help='Run full sync (ignore last sync)')
    parser.add_argument('--loop', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=300, help='Sync interval in seconds (default: 300)')
    
    args = parser.parse_args()
    
    service = LeadSyncService()
    
    if args.loop:
        logger.info(f"Starting continuous sync (interval: {args.interval}s)")
        while True:
            try:
                service.run_sync(full_sync=args.full)
                args.full = False  # Only full sync on first run
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            import time
            time.sleep(args.interval)
    else:
        service.run_sync(full_sync=args.full)


if __name__ == "__main__":
    main()