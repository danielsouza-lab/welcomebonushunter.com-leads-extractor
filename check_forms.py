#!/usr/bin/env python3
"""Check for form data in WordPress posts and pages."""

import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

# Get credentials
site_url = os.getenv('WORDPRESS_URL')
username = os.getenv('WORDPRESS_USERNAME')
password = os.getenv('WORDPRESS_PASSWORD')

# Setup authentication
credentials = base64.b64encode(f"{username}:{password}".encode()).decode('ascii')
headers = {'Authorization': f'Basic {credentials}'}

print("=" * 60)
print("Searching for sweeprewards-signups page and form data")
print("=" * 60)

# 1. Search for pages with "sweep" or "signup" in the slug
print("\n1. Searching for relevant pages...")
try:
    response = requests.get(
        f"{site_url}/wp-json/wp/v2/pages",
        headers=headers,
        params={'per_page': 100, 'search': 'sweep'}
    )
    
    if response.status_code == 200:
        pages = response.json()
        print(f"Found {len(pages)} pages with 'sweep' in content")
        
        for page in pages:
            print(f"\n  Page: {page.get('title', {}).get('rendered', 'Unknown')}")
            print(f"  Slug: {page.get('slug')}")
            print(f"  ID: {page.get('id')}")
            print(f"  Link: {page.get('link')}")
            
    # Also search for "signup"
    response = requests.get(
        f"{site_url}/wp-json/wp/v2/pages",
        headers=headers,
        params={'per_page': 100, 'slug': 'sweeprewards-signups'}
    )
    
    if response.status_code == 200:
        pages = response.json()
        if pages:
            print(f"\n[FOUND] Page with slug 'sweeprewards-signups':")
            for page in pages:
                print(f"  Title: {page.get('title', {}).get('rendered', 'Unknown')}")
                print(f"  ID: {page.get('id')}")
                print(f"  Link: {page.get('link')}")
                
except Exception as e:
    print(f"Error searching pages: {e}")

# 2. Check for custom post types
print("\n2. Checking for custom post types...")
try:
    response = requests.get(
        f"{site_url}/wp-json/wp/v2/types",
        headers=headers
    )
    
    if response.status_code == 200:
        post_types = response.json()
        print(f"Available post types: {', '.join(post_types.keys())}")
        
        # Check if there are any form-related custom post types
        for post_type, details in post_types.items():
            if any(keyword in post_type.lower() for keyword in ['form', 'lead', 'submission', 'entry', 'signup']):
                print(f"\n[INTERESTING] Found post type: {post_type}")
                print(f"  Name: {details.get('name')}")
                print(f"  Rest base: {details.get('rest_base')}")
                
                # Try to fetch entries
                if details.get('rest_base'):
                    try:
                        entries_response = requests.get(
                            f"{site_url}/wp-json/wp/v2/{details.get('rest_base')}",
                            headers=headers,
                            params={'per_page': 10}
                        )
                        if entries_response.status_code == 200:
                            entries = entries_response.json()
                            print(f"  Found {len(entries)} entries")
                    except:
                        pass
                        
except Exception as e:
    print(f"Error checking post types: {e}")

# 3. Check database tables (via custom endpoint if available)
print("\n3. Checking for form submission storage...")
print("Note: Direct database access would show tables like:")
print("  - wp_db7_forms (Contact Form 7 Database addon)")
print("  - wp_wpforms_entries (WPForms)")
print("  - wp_gf_entry (Gravity Forms)")
print("  - wp_frm_items (Formidable)")
print("  - Custom tables for sweepstakes")

# 4. Check admin-ajax.php actions
print("\n4. Common AJAX actions for forms...")
print("The site likely uses admin-ajax.php for form processing.")
print("Without access to the PHP code, we can't see the registered actions.")
print("\nTo extract leads, you'll need one of these:")
print("  1. Install a form storage plugin (like Flamingo for CF7)")
print("  2. Direct database access to query submission tables")
print("  3. Export functionality in the WordPress admin panel")
print("  4. Custom plugin to expose the data via REST API")

print("\n" + "=" * 60)
print("Analysis complete")
print("=" * 60)