#!/usr/bin/env python3
"""Test the Rolling Riches Leads API plugin."""

import os
import requests
import base64
import json
from datetime import datetime, timedelta
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
print("Rolling Riches Leads API Test")
print("=" * 60)
print("\nNOTE: Make sure you've installed and activated the")
print("'Rolling Riches Leads API' plugin in WordPress first!")
print("=" * 60)

# 1. Test the stats endpoint first
print("\n1. Checking leads statistics...")
try:
    response = requests.get(
        f"{site_url}/wp-json/rolling-riches/v1/leads/stats",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        stats = response.json()
        print("[SUCCESS] Stats endpoint working!")
        print("\nTables checked:")
        for table, info in stats.get('tables_checked', {}).items():
            if info['exists']:
                print(f"  [FOUND] {table}: {info['count']} entries")
            else:
                print(f"  [NOT FOUND] {table}")
                
        if stats.get('all_tables'):
            print("\nOther potential form tables found:")
            for table, count in stats.get('all_tables', {}).items():
                print(f"  - {table}: {count} entries")
                
        print(f"\nTotal leads found: {stats.get('leads_count', 0)}")
        
    elif response.status_code == 404:
        print("[ERROR] Plugin endpoint not found. Please install and activate the plugin.")
        print("\nTo install:")
        print("1. ZIP the wordpress-plugin/rolling-riches-leads-api folder")
        print("2. Upload via WordPress Admin -> Plugins -> Add New -> Upload Plugin")
        print("3. Activate the plugin")
        exit(1)
    elif response.status_code == 401:
        print("[ERROR] Authentication failed")
    else:
        print(f"[ERROR] Stats request failed with status {response.status_code}")
        
except Exception as e:
    print(f"[ERROR] Failed to connect: {e}")
    exit(1)

# 2. Get the actual leads
print("\n2. Fetching leads...")
try:
    # Get leads from the last 90 days
    since_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    response = requests.get(
        f"{site_url}/wp-json/rolling-riches/v1/leads",
        headers=headers,
        params={
            'since': since_date,
            'limit': 100
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"[SUCCESS] Leads endpoint working!")
        print(f"\nResponse: {data.get('message', '')}")
        print(f"Found table: {data.get('found_table', 'None')}")
        print(f"Total leads returned: {data.get('total', 0)}")
        
        leads = data.get('leads', [])
        if leads:
            print(f"\nFirst 5 leads:")
            print("-" * 40)
            for i, lead in enumerate(leads[:5], 1):
                print(f"\nLead #{i}:")
                print(f"  ID: {lead.get('id')}")
                print(f"  Email: {lead.get('email', 'N/A')}")
                print(f"  Name: {lead.get('name', 'N/A')}")
                print(f"  Date: {lead.get('date', 'N/A')}")
                
                # Show raw data fields
                if lead.get('raw_data'):
                    print("  Raw data fields:")
                    for key in list(lead['raw_data'].keys())[:5]:
                        value = str(lead['raw_data'][key])[:50]
                        print(f"    - {key}: {value}")
                        
            # Save to file for analysis
            with open('extracted_leads.json', 'w') as f:
                json.dump(leads, f, indent=2, default=str)
            print(f"\n[SUCCESS] All {len(leads)} leads saved to 'extracted_leads.json'")
            
        else:
            print("\nNo leads found. This could mean:")
            print("  - The table structure is different than expected")
            print("  - No signups in the date range")
            print("  - Data is stored in a non-standard way")
            
    else:
        print(f"[ERROR] Leads request failed with status {response.status_code}")
        if response.text:
            print(f"Response: {response.text[:500]}")
            
except Exception as e:
    print(f"[ERROR] Failed to fetch leads: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)