#!/usr/bin/env python3
"""
Sync leads from MySQL database to Go High Level CRM.
Includes retry logic and response logging.
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pymysql
from dotenv import load_dotenv
from src.wordpress_leads_extractor.api.ghl_client import GHLClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ghl_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GHLSyncManager:
    """Manages syncing leads to Go High Level."""
    
    def __init__(self):
        """Initialize sync manager with database and GHL client."""
        # Database configuration
        self.db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        
        # GHL configuration
        self.ghl_client = GHLClient(
            access_token=os.getenv('GHL_ACCESS_TOKEN'),
            location_id=os.getenv('GHL_LOCATION_ID'),
            api_version=os.getenv('GHL_API_VERSION', '2021-07-28')
        )
        
        # Sync configuration
        self.batch_size = int(os.getenv('GHL_BATCH_SIZE', 10))
        self.max_retries = int(os.getenv('GHL_MAX_RETRIES', 3))
        self.retry_delay_minutes = int(os.getenv('GHL_RETRY_DELAY_MINUTES', 30))
        
    def get_db_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.db_config)
    
    def get_leads_to_sync(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get leads that need to be synced to GHL.
        
        Args:
            limit: Maximum number of leads to return
            
        Returns:
            List of lead dictionaries
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Query for unsynced leads and retries
                query = """
                SELECT DISTINCT
                    l.id,
                    l.email,
                    l.phone,
                    l.first_name,
                    l.last_name,
                    l.signup_date,
                    l.quality_score,
                    l.ghl_sync_attempts,
                    COALESCE(latest_log.retry_count, 0) as retry_count,
                    latest_log.status as last_status,
                    latest_log.next_retry_at
                FROM leads l
                LEFT JOIN (
                    SELECT 
                        lead_id,
                        status,
                        retry_count,
                        next_retry_at,
                        ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY id DESC) as rn
                    FROM ghl_sync_log
                ) latest_log ON l.id = latest_log.lead_id AND latest_log.rn = 1
                WHERE 
                    (l.ghl_synced = FALSE AND l.id NOT IN (SELECT DISTINCT lead_id FROM ghl_sync_log))
                    OR (
                        latest_log.status IN ('failed', 'retry') 
                        AND latest_log.retry_count < %s
                        AND (latest_log.next_retry_at IS NULL OR latest_log.next_retry_at <= NOW())
                    )
                ORDER BY 
                    CASE WHEN latest_log.status = 'retry' THEN 0 ELSE 1 END,
                    l.quality_score DESC,
                    l.signup_date ASC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                else:
                    query += f" LIMIT {self.batch_size}"
                
                cursor.execute(query, (self.max_retries,))
                return cursor.fetchall()
                
        finally:
            conn.close()
    
    def log_sync_attempt(
        self,
        lead_id: int,
        email: str,
        result: Dict[str, Any]
    ):
        """
        Log GHL sync attempt to database.
        
        Args:
            lead_id: Lead ID
            email: Lead email
            result: Response from GHL API
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Determine status
                if result.get("success"):
                    status = "success"
                    next_retry = None
                else:
                    status = "failed"
                    # Calculate next retry time
                    next_retry = datetime.now() + timedelta(minutes=self.retry_delay_minutes)
                
                # Get current retry count
                cursor.execute(
                    "SELECT MAX(retry_count) FROM ghl_sync_log WHERE lead_id = %s",
                    (lead_id,)
                )
                current_retry = cursor.fetchone()[0] or 0
                
                # Insert log entry
                insert_query = """
                INSERT INTO ghl_sync_log (
                    lead_id,
                    email,
                    request_timestamp,
                    request_body,
                    response_status_code,
                    response_body,
                    response_timestamp,
                    status,
                    error_message,
                    retry_count,
                    next_retry_at,
                    ghl_contact_id,
                    ghl_location_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                
                cursor.execute(insert_query, (
                    lead_id,
                    email,
                    result.get("request_timestamp"),
                    json.dumps(result.get("request_body")),
                    result.get("response_status_code"),
                    json.dumps(result.get("response_body")),
                    result.get("response_timestamp"),
                    status,
                    result.get("error_message"),
                    current_retry + (1 if status == "failed" else 0),
                    next_retry,
                    result.get("ghl_contact_id"),
                    self.ghl_client.location_id
                ))
                
                # Update lead if successful
                if status == "success" and result.get("ghl_contact_id"):
                    cursor.execute("""
                        UPDATE leads 
                        SET 
                            ghl_synced = TRUE,
                            ghl_synced_at = NOW(),
                            ghl_contact_id = %s,
                            ghl_sync_attempts = ghl_sync_attempts + 1
                        WHERE id = %s
                    """, (result.get("ghl_contact_id"), lead_id))
                else:
                    # Just increment attempts
                    cursor.execute("""
                        UPDATE leads 
                        SET ghl_sync_attempts = ghl_sync_attempts + 1
                        WHERE id = %s
                    """, (lead_id,))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to log sync attempt: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
    
    def sync_lead(self, lead: Dict[str, Any]) -> bool:
        """
        Sync a single lead to GHL.
        
        Args:
            lead: Lead data dictionary
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Syncing lead {lead['id']}: {lead['email']}")
            
            # Prepare tags based on quality score
            tags = []
            if lead.get('quality_score', 0) >= 80:
                tags.append("high-quality")
            elif lead.get('quality_score', 0) >= 50:
                tags.append("medium-quality")
            else:
                tags.append("low-quality")
            
            tags.append("wordpress-lead")
            tags.append(f"signup-{lead['signup_date'].strftime('%Y-%m')}")
            
            # Custom fields
            custom_fields = {
                "signup_date": lead['signup_date'].isoformat() if lead.get('signup_date') else None,
                "quality_score": str(lead.get('quality_score', 0)),
                "source": "WordPress Sweepstakes"
            }
            
            # Create or update contact in GHL
            result = self.ghl_client.create_or_update_contact(
                email=lead['email'],
                phone=lead.get('phone'),
                first_name=lead.get('first_name'),
                last_name=lead.get('last_name'),
                tags=tags,
                custom_fields=custom_fields,
                source="WordPress Lead Form"
            )
            
            # Log the attempt
            self.log_sync_attempt(lead['id'], lead['email'], result)
            
            if result.get("success"):
                logger.info(f"[SUCCESS] Synced {lead['email']} - GHL ID: {result.get('ghl_contact_id')}")
                return True
            else:
                logger.warning(f"[FAILED] Failed to sync {lead['email']}: {result.get('error_message')}")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing lead {lead['id']}: {str(e)}")
            # Log the error
            error_result = {
                "request_timestamp": datetime.utcnow().isoformat(),
                "request_body": {"email": lead['email']},
                "response_status_code": None,
                "response_body": None,
                "response_timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error_message": str(e),
                "ghl_contact_id": None
            }
            self.log_sync_attempt(lead['id'], lead['email'], error_result)
            return False
    
    def sync_batch(self, batch_size: Optional[int] = None) -> Dict[str, int]:
        """
        Sync a batch of leads.
        
        Args:
            batch_size: Number of leads to sync (uses default if None)
            
        Returns:
            Dictionary with success/failure counts
        """
        leads = self.get_leads_to_sync(limit=batch_size)
        
        if not leads:
            logger.info("No leads to sync")
            return {"total": 0, "success": 0, "failed": 0}
        
        logger.info(f"Found {len(leads)} leads to sync")
        
        results = {"total": len(leads), "success": 0, "failed": 0}
        
        for lead in leads:
            if self.sync_lead(lead):
                results["success"] += 1
            else:
                results["failed"] += 1
            
            # Small delay between requests to avoid rate limiting
            time.sleep(0.5)
        
        logger.info(f"Sync batch complete: {results}")
        return results
    
    def retry_failed_leads(self, date: Optional[datetime] = None) -> Dict[str, int]:
        """
        Retry all failed leads from a specific date.
        
        Args:
            date: Date to retry (defaults to today)
            
        Returns:
            Dictionary with retry results
        """
        if date is None:
            date = datetime.now().date()
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Mark all failed leads for retry
                cursor.execute("""
                    UPDATE ghl_sync_log
                    SET 
                        status = 'retry',
                        next_retry_at = NOW()
                    WHERE 
                        DATE(request_timestamp) = %s
                        AND status = 'failed'
                        AND retry_count < %s
                """, (date, self.max_retries))
                
                marked_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Marked {marked_count} failed leads for retry")
                
                # Now sync them
                if marked_count > 0:
                    return self.sync_batch(batch_size=marked_count)
                else:
                    return {"total": 0, "success": 0, "failed": 0}
                    
        finally:
            conn.close()
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get current sync statistics."""
        conn = self.get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT lead_id) as total_leads_attempted,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_syncs,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_syncs,
                        SUM(CASE WHEN status = 'retry' THEN 1 ELSE 0 END) as pending_retries,
                        MAX(request_timestamp) as last_sync_attempt
                    FROM ghl_sync_log
                """)
                overall_stats = cursor.fetchone()
                
                # Today's stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT lead_id) as leads_synced_today,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_today,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_today
                    FROM ghl_sync_log
                    WHERE DATE(request_timestamp) = CURDATE()
                """)
                today_stats = cursor.fetchone()
                
                # Pending leads
                cursor.execute("""
                    SELECT COUNT(*) as pending_leads
                    FROM leads
                    WHERE ghl_synced = FALSE
                """)
                pending = cursor.fetchone()
                
                return {
                    "overall": overall_stats,
                    "today": today_stats,
                    "pending_leads": pending['pending_leads']
                }
                
        finally:
            conn.close()
    
    def continuous_sync(self, interval_minutes: int = 10):
        """
        Run continuous sync with specified interval.
        
        Args:
            interval_minutes: Minutes between sync runs
        """
        logger.info(f"Starting continuous sync - running every {interval_minutes} minutes")
        
        while True:
            try:
                # Run sync
                results = self.sync_batch()
                
                # Check if it's end of day (e.g., 11 PM)
                now = datetime.now()
                if now.hour == 23 and now.minute < interval_minutes:
                    logger.info("Running end-of-day retry for failed leads")
                    retry_results = self.retry_failed_leads()
                    logger.info(f"End-of-day retry results: {retry_results}")
                
                # Wait for next run
                logger.info(f"Waiting {interval_minutes} minutes until next sync...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Stopping continuous sync")
                break
            except Exception as e:
                logger.error(f"Error in continuous sync: {str(e)}")
                time.sleep(60)  # Wait 1 minute on error


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync leads to Go High Level")
    parser.add_argument('--once', action='store_true', help='Run sync once and exit')
    parser.add_argument('--batch-size', type=int, help='Number of leads to sync')
    parser.add_argument('--retry-failed', action='store_true', help='Retry all failed leads from today')
    parser.add_argument('--stats', action='store_true', help='Show sync statistics')
    parser.add_argument('--test', action='store_true', help='Test GHL connection')
    parser.add_argument('--continuous', action='store_true', help='Run continuous sync')
    parser.add_argument('--interval', type=int, default=10, help='Sync interval in minutes (default: 10)')
    
    args = parser.parse_args()
    
    # Check required environment variables
    required_vars = ['GHL_ACCESS_TOKEN', 'GHL_LOCATION_ID', 'MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Initialize sync manager
    sync_manager = GHLSyncManager()
    
    # Handle different modes
    if args.test:
        logger.info("Testing GHL connection...")
        if sync_manager.ghl_client.test_connection():
            print("[SUCCESS] GHL connection test passed")
        else:
            print("[ERROR] GHL connection test failed")
            sys.exit(1)
            
    elif args.stats:
        stats = sync_manager.get_sync_stats()
        print("\n=== GHL Sync Statistics ===")
        print(f"\nOverall:")
        print(f"  Total leads attempted: {stats['overall']['total_leads_attempted']}")
        print(f"  Successful syncs: {stats['overall']['successful_syncs']}")
        print(f"  Failed syncs: {stats['overall']['failed_syncs']}")
        print(f"  Pending retries: {stats['overall']['pending_retries']}")
        print(f"  Last sync: {stats['overall']['last_sync_attempt']}")
        print(f"\nToday:")
        print(f"  Leads synced: {stats['today']['leads_synced_today']}")
        print(f"  Successful: {stats['today']['successful_today']}")
        print(f"  Failed: {stats['today']['failed_today']}")
        print(f"\nPending:")
        print(f"  Unsynced leads: {stats['pending_leads']}")
        
    elif args.retry_failed:
        logger.info("Retrying failed leads from today...")
        results = sync_manager.retry_failed_leads()
        print(f"Retry results: {results}")
        
    elif args.continuous:
        sync_manager.continuous_sync(interval_minutes=args.interval)
        
    else:
        # Run once
        results = sync_manager.sync_batch(batch_size=args.batch_size)
        print(f"Sync results: {results}")


if __name__ == "__main__":
    main()