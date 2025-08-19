#!/usr/bin/env python3
"""Demo GHL sync without database - just to show it working."""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.wordpress_leads_extractor.api.ghl_client import GHLClient

# Load environment
load_dotenv()

def sync_demo_leads():
    """Sync some demo leads to GHL to show the integration works."""
    
    # Initialize GHL client
    client = GHLClient(
        access_token=os.getenv('GHL_ACCESS_TOKEN'),
        location_id=os.getenv('GHL_LOCATION_ID')
    )
    
    # Create some demo leads
    demo_leads = [
        {
            "email": f"john.doe.{datetime.now().strftime('%Y%m%d')}@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+15551234001",
            "quality_score": 85,
            "signup_date": datetime.now() - timedelta(days=1)
        },
        {
            "email": f"jane.smith.{datetime.now().strftime('%Y%m%d')}@example.com", 
            "first_name": "Jane",
            "last_name": "Smith",
            "phone": "+15551234002",
            "quality_score": 92,
            "signup_date": datetime.now() - timedelta(days=2)
        },
        {
            "email": f"bob.johnson.{datetime.now().strftime('%Y%m%d')}@example.com",
            "first_name": "Bob", 
            "last_name": "Johnson",
            "phone": "+15551234003",
            "quality_score": 67,
            "signup_date": datetime.now() - timedelta(days=3)
        }
    ]
    
    print("=" * 60)
    print("GO HIGH LEVEL SYNC DEMO")
    print("=" * 60)
    print(f"\nSyncing {len(demo_leads)} demo leads to GHL...\n")
    
    success_count = 0
    failed_count = 0
    
    for lead in demo_leads:
        print(f"Syncing: {lead['email']}")
        
        # Determine quality tag
        tags = ["wordpress-lead", "demo"]
        if lead['quality_score'] >= 80:
            tags.append("high-quality")
        elif lead['quality_score'] >= 50:
            tags.append("medium-quality")
        else:
            tags.append("low-quality")
        
        # Add signup month tag
        tags.append(f"signup-{lead['signup_date'].strftime('%Y-%m')}")
        
        # Custom fields
        custom_fields = {
            "quality_score": str(lead['quality_score']),
            "signup_date": lead['signup_date'].isoformat(),
            "source": "WordPress Sweepstakes Demo"
        }
        
        # Create contact in GHL
        result = client.create_or_update_contact(
            email=lead['email'],
            phone=lead['phone'],
            first_name=lead['first_name'],
            last_name=lead['last_name'],
            tags=tags,
            custom_fields=custom_fields,
            source="WordPress Demo"
        )
        
        if result.get("success"):
            success_count += 1
            print(f"  [SUCCESS] Created - GHL ID: {result.get('ghl_contact_id')}")
            print(f"  Tags: {', '.join(tags)}")
            print(f"  Quality Score: {lead['quality_score']}")
        else:
            failed_count += 1
            print(f"  [FAILED] {result.get('error_message')}")
        
        print()
    
    print("=" * 60)
    print("SYNC SUMMARY")
    print("=" * 60)
    print(f"Total Leads: {len(demo_leads)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    
    if success_count > 0:
        print("\n[SUCCESS] Demo sync completed!")
        print("\nNext steps:")
        print("1. Check your GHL contacts - you should see the new leads")
        print("2. Look for the tags: 'wordpress-lead', 'demo', quality tags")
        print("3. Check the custom fields for quality_score and signup_date")
        print("\nTo sync real leads from MySQL:")
        print("1. Add MySQL credentials to your .env file:")
        print("   MYSQL_HOST=your-host")
        print("   MYSQL_USER=your-user")
        print("   MYSQL_PASSWORD=your-password")
        print("   MYSQL_DATABASE=your-database")
        print("2. Apply the database schema: mysql -u user -p < ghl_schema_update.sql")
        print("3. Run: python3 sync_to_ghl.py --once")
    
    return success_count > 0

if __name__ == "__main__":
    success = sync_demo_leads()
    sys.exit(0 if success else 1)