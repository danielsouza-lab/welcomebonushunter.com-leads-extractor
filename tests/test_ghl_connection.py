#!/usr/bin/env python3
"""Test Go High Level API connection and credentials."""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.wordpress_leads_extractor.api.ghl_client import GHLClient

# Load GHL-specific environment variables
load_dotenv('.env.ghl')

def test_ghl_connection():
    """Test GHL API connection and show account info."""
    
    # Get credentials
    access_token = os.getenv('GHL_ACCESS_TOKEN')
    location_id = os.getenv('GHL_LOCATION_ID')
    
    if not access_token or not location_id:
        print("[ERROR] Missing GHL credentials in .env.ghl file")
        return False
    
    print("=" * 50)
    print("GO HIGH LEVEL CONNECTION TEST")
    print("=" * 50)
    print(f"\nLocation ID: {location_id}")
    print(f"Token (first 20 chars): {access_token[:20]}...")
    
    # Initialize client
    print("\nInitializing GHL client...")
    client = GHLClient(
        access_token=access_token,
        location_id=location_id
    )
    
    # Test connection
    print("Testing API connection...")
    if client.test_connection():
        print("[SUCCESS] Connection successful!")
        
        # Try to create a test contact
        print("\nTesting contact creation...")
        test_email = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
        
        result = client.create_contact(
            email=test_email,
            first_name="Test",
            last_name="Lead",
            phone="+15551234567",
            tags=["test", "api-verification"],
            source="API Test"
        )
        
        if result.get("success"):
            print(f"[SUCCESS] Test contact created!")
            print(f"  Email: {test_email}")
            print(f"  GHL Contact ID: {result.get('ghl_contact_id')}")
            
            # Try to search for the contact
            print("\nVerifying contact search...")
            found = client.get_contact_by_email(test_email)
            if found:
                print(f"[SUCCESS] Contact found via search")
                print(f"  Contact Name: {found.get('firstName')} {found.get('lastName')}")
            else:
                print("[WARNING] Contact created but not found in search")
                
        else:
            print(f"[ERROR] Failed to create test contact")
            print(f"  Status Code: {result.get('response_status_code')}")
            print(f"  Error: {result.get('error_message')}")
            
            # Check if it's a duplicate error
            if "duplicate" in str(result.get('error_message', '')).lower():
                print("[INFO] This might be a duplicate contact error (expected if you've run this test before)")
        
        print("\n" + "=" * 50)
        print("CONFIGURATION SUMMARY")
        print("=" * 50)
        print("\nAdd these to your main .env file:")
        print(f"GHL_ACCESS_TOKEN={access_token}")
        print(f"GHL_LOCATION_ID={location_id}")
        print("\nYour GHL integration is ready to use!")
        print("\nNext steps:")
        print("1. Copy the credentials above to your .env file")
        print("2. Run: python sync_to_ghl.py --once")
        print("3. Check your GHL contacts for the synced leads")
        
        return True
    else:
        print("[ERROR] Connection failed!")
        print("\nPossible issues:")
        print("1. Invalid API token")
        print("2. Token doesn't have required permissions")
        print("3. Location ID doesn't match the token")
        print("4. Network connectivity issues")
        return False

if __name__ == "__main__":
    success = test_ghl_connection()
    sys.exit(0 if success else 1)