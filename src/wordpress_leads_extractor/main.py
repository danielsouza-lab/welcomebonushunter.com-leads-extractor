"""Main script for extracting WordPress leads and saving to database."""

import os
import sys
import logging
import argparse
import schedule
import time
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.wordpress_leads_extractor.api.wordpress_client import WordPressClient
from src.wordpress_leads_extractor.database.connection import DatabaseManager, LeadRepository
from src.wordpress_leads_extractor.models.lead import LeadSchema

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wordpress_leads_extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LeadsExtractor:
    """Main class for extracting and processing WordPress leads."""
    
    def __init__(self):
        """Initialize the leads extractor with configuration from environment."""
        # WordPress configuration
        self.wp_url = os.getenv('WORDPRESS_URL', '').rstrip('/')
        self.wp_username = os.getenv('WORDPRESS_USERNAME', '')
        self.wp_password = os.getenv('WORDPRESS_PASSWORD', '')
        self.use_app_password = os.getenv('WORDPRESS_USE_APP_PASSWORD', 'false').lower() == 'true'
        
        # Database configuration
        self.db_url = os.getenv('DATABASE_URL', 'sqlite:///leads.db')
        
        # Extraction configuration
        self.extraction_interval = int(os.getenv('EXTRACTION_INTERVAL_MINUTES', '60'))
        self.look_back_days = int(os.getenv('LOOK_BACK_DAYS', '7'))
        
        # Initialize components
        self.wp_client: Optional[WordPressClient] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.lead_repo: Optional[LeadRepository] = None
        
        self._validate_configuration()
        
    def _validate_configuration(self):
        """Validate required configuration."""
        if not self.wp_url:
            raise ValueError("WORDPRESS_URL is required")
        if not self.wp_username:
            raise ValueError("WORDPRESS_USERNAME is required")
        if not self.wp_password:
            raise ValueError("WORDPRESS_PASSWORD is required")
            
        logger.info(f"Configuration validated for {self.wp_url}")
    
    def initialize(self):
        """Initialize WordPress client and database connection."""
        try:
            # Initialize WordPress client
            logger.info("Initializing WordPress client...")
            self.wp_client = WordPressClient(
                site_url=self.wp_url,
                username=self.wp_username,
                password=self.wp_password,
                use_application_password=self.use_app_password
            )
            
            if not self.wp_client.test_connection():
                raise ConnectionError("Failed to connect to WordPress API")
            
            # Initialize database
            logger.info("Initializing database connection...")
            self.db_manager = DatabaseManager(self.db_url)
            
            if not self.db_manager.test_connection():
                raise ConnectionError("Failed to connect to database")
            
            # Create tables if they don't exist
            self.db_manager.create_tables()
            
            # Initialize repository
            self.lead_repo = LeadRepository(self.db_manager)
            
            logger.info("Initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    def extract_leads(self, since: Optional[datetime] = None):
        """
        Extract leads from WordPress.
        
        Args:
            since: Extract leads since this datetime (default: look_back_days ago)
        """
        if not since:
            since = datetime.utcnow() - timedelta(days=self.look_back_days)
            
        logger.info(f"Extracting leads since {since.isoformat()}")
        
        try:
            # Get all leads from WordPress
            leads = self.wp_client.get_all_leads(since=since)
            
            if not leads:
                logger.info("No new leads found")
                return
            
            logger.info(f"Found {len(leads)} leads to process")
            
            # Save leads to database
            saved_count = 0
            updated_count = 0
            error_count = 0
            
            for lead_data in leads:
                try:
                    lead_id = self.lead_repo.save_lead(lead_data)
                    if lead_id:
                        if 'updated' in str(lead_id):
                            updated_count += 1
                        else:
                            saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving lead: {e}")
                    error_count += 1
            
            logger.info(f"Extraction completed: {saved_count} new, {updated_count} updated, {error_count} errors")
            
        except Exception as e:
            logger.error(f"Error during extraction: {e}")
            raise
    
    def process_unprocessed_leads(self):
        """Process any unprocessed leads in the database."""
        logger.info("Processing unprocessed leads...")
        
        try:
            unprocessed = self.lead_repo.get_unprocessed_leads(limit=100)
            
            if not unprocessed:
                logger.info("No unprocessed leads found")
                return
            
            logger.info(f"Found {len(unprocessed)} unprocessed leads")
            
            for lead in unprocessed:
                # Here you can add custom processing logic
                # For example: send to CRM, send email notification, etc.
                
                # Mark as processed
                self.lead_repo.mark_lead_processed(
                    lead['id'],
                    notes=f"Processed at {datetime.utcnow().isoformat()}"
                )
                
                logger.info(f"Processed lead: {lead['email']}")
                
        except Exception as e:
            logger.error(f"Error processing leads: {e}")
    
    def get_statistics(self):
        """Get extraction statistics."""
        try:
            total_leads = self.lead_repo.get_leads_count()
            unprocessed_leads = self.lead_repo.get_leads_count(processed=False)
            
            stats = {
                'total_leads': total_leads,
                'unprocessed_leads': unprocessed_leads,
                'processed_leads': total_leads - unprocessed_leads
            }
            
            # Get counts by source
            for source in ['contact_form_7', 'wpforms', 'gravity_forms', 'wordpress_comment']:
                stats[f'{source}_count'] = self.lead_repo.get_leads_count(source=source)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def run_extraction_job(self):
        """Run a single extraction job."""
        logger.info("=" * 50)
        logger.info("Starting extraction job")
        
        try:
            # Extract new leads
            self.extract_leads()
            
            # Process unprocessed leads
            self.process_unprocessed_leads()
            
            # Log statistics
            stats = self.get_statistics()
            logger.info(f"Statistics: {stats}")
            
            logger.info("Extraction job completed")
            
        except Exception as e:
            logger.error(f"Extraction job failed: {e}")
    
    def run_scheduled(self):
        """Run the extractor on a schedule."""
        logger.info(f"Starting scheduled extraction (every {self.extraction_interval} minutes)")
        
        # Run immediately
        self.run_extraction_job()
        
        # Schedule regular runs
        schedule.every(self.extraction_interval).minutes.do(self.run_extraction_job)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduled extraction stopped by user")
        except Exception as e:
            logger.error(f"Scheduled extraction error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        if self.db_manager:
            self.db_manager.close()
        logger.info("Cleanup completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Extract WordPress leads to database')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run extraction once and exit'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of days to look back for leads'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics and exit'
    )
    
    args = parser.parse_args()
    
    try:
        # Create and initialize extractor
        extractor = LeadsExtractor()
        
        if args.days:
            extractor.look_back_days = args.days
            
        extractor.initialize()
        
        if args.stats:
            # Show statistics only
            stats = extractor.get_statistics()
            print("\nLead Extraction Statistics:")
            print("-" * 30)
            for key, value in stats.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        elif args.once:
            # Run once
            extractor.run_extraction_job()
        else:
            # Run scheduled
            extractor.run_scheduled()
            
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        logger.info("Application stopped")


if __name__ == "__main__":
    main()