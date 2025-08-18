#!/usr/bin/env python3
"""Test WordPress connection and attempt to fetch leads."""

import os
import sys
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from src.wordpress_leads_extractor.api.wordpress_client import WordPressClient
from src.wordpress_leads_extractor.database.connection import DatabaseManager, LeadRepository

# Load environment variables
load_dotenv()

def test_wordpress_connection():
    """Test the WordPress connection and fetch leads."""
    
    print("=" * 60)
    print("WordPress Leads Extractor - Connection Test")
    print("=" * 60)
    
    # Get credentials from environment
    wp_url = os.getenv('WORDPRESS_URL')
    wp_username = os.getenv('WORDPRESS_USERNAME')
    wp_password = os.getenv('WORDPRESS_PASSWORD')
    
    print(f"\nConnecting to: {wp_url}")
    print(f"Username: {wp_username}")
    print(f"Password: {'*' * len(wp_password)}")
    
    try:
        # Initialize WordPress client
        print("\n1. Testing WordPress API connection...")
        use_app_pass = os.getenv('WORDPRESS_USE_APP_PASSWORD', 'false').lower() == 'true'
        client = WordPressClient(
            site_url=wp_url,
            username=wp_username,
            password=wp_password,
            use_application_password=use_app_pass
        )
        
        if client.test_connection():
            print("[SUCCESS] Successfully connected to WordPress!")
        else:
            print("[ERROR] Failed to connect to WordPress")
            return
        
        # Try to fetch leads from the last 30 days
        print("\n2. Attempting to fetch leads from the last 30 days...")
        since = datetime.utcnow() - timedelta(days=30)
        
        # Try different sources
        print("\n   Checking Contact Form 7...")
        cf7_leads = client.get_contact_form_7_submissions(since=since)
        print(f"   Found {len(cf7_leads)} Contact Form 7 submissions")
        
        print("\n   Checking WPForms...")
        wpforms_leads = client.get_wpforms_submissions(since=since)
        print(f"   Found {len(wpforms_leads)} WPForms submissions")
        
        print("\n   Checking Gravity Forms...")
        gf_leads = client.get_gravity_forms_entries(since=since)
        print(f"   Found {len(gf_leads)} Gravity Forms entries")
        
        print("\n   Checking WordPress comments...")
        comment_leads = client.get_comments_as_leads(since=since)
        print(f"   Found {len(comment_leads)} comments")
        
        # Get all leads
        print("\n3. Fetching all leads...")
        all_leads = client.get_all_leads(since=since)
        print(f"\n[SUCCESS] Total leads found: {len(all_leads)}")
        
        if all_leads:
            print("\n4. Sample lead data (first 3 leads):")
            print("-" * 40)
            for i, lead in enumerate(all_leads[:3], 1):
                print(f"\nLead #{i}:")
                print(f"  Source: {lead.get('source')}")
                print(f"  Date: {lead.get('date')}")
                print(f"  Name: {lead.get('name', 'N/A')}")
                print(f"  Email: {lead.get('email', 'N/A')}")
                if 'fields' in lead:
                    print(f"  Fields: {json.dumps(lead['fields'], indent=4)[:200]}...")
                    
            # Save to database
            print("\n5. Saving to database...")
            db_manager = DatabaseManager("sqlite:///test_leads.db")
            db_manager.create_tables()
            
            if db_manager.test_connection():
                print("[SUCCESS] Database connection successful")
                
                repo = LeadRepository(db_manager)
                saved_count = 0
                
                for lead in all_leads:
                    lead_id = repo.save_lead(lead)
                    if lead_id:
                        saved_count += 1
                        
                print(f"[SUCCESS] Saved {saved_count} leads to database")
                
                # Show statistics
                total = repo.get_leads_count()
                print(f"\nDatabase Statistics:")
                print(f"  Total leads: {total}")
                
                db_manager.close()
        else:
            print("\n[WARNING] No leads found. This could mean:")
            print("  - The form plugin might not have API support enabled")
            print("  - No submissions in the last 30 days")
            print("  - Need to install Flamingo plugin for Contact Form 7")
            print("  - Different form plugin is being used")
            
            # Let's check what's available on the site
            print("\n6. Checking available REST API endpoints...")
            import requests
            from requests.auth import HTTPBasicAuth
            
            response = requests.get(
                f"{wp_url}/wp-json/",
                auth=HTTPBasicAuth(wp_username, wp_password)
            )
            
            if response.status_code == 200:
                data = response.json()
                namespaces = data.get('namespaces', [])
                print(f"Available API namespaces: {', '.join(namespaces)}")
                
                # Check for form-related endpoints
                form_namespaces = [ns for ns in namespaces if any(
                    keyword in ns.lower() for keyword in 
                    ['form', 'contact', 'wpforms', 'gravity', 'flamingo', 'sweep']
                )]
                
                if form_namespaces:
                    print(f"\nForm-related namespaces found: {', '.join(form_namespaces)}")
                else:
                    print("\n[WARNING] No standard form API endpoints found")
                    
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_wordpress_connection()