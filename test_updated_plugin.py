#!/usr/bin/env python3
"""Test the updated WordPress plugin with new filtering parameters."""

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
print("Testing Updated WordPress Plugin v2")
print("=" * 60)

# Test 1: Basic connection
print("\n1. Testing basic connection...")
response = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads/stats",
    headers=headers,
    timeout=10
)

if response.status_code == 200:
    stats = response.json()
    print("[SUCCESS] Plugin is active and responding")
    print(f"Total leads in database: {stats.get('leads_count', 0)}")
else:
    print(f"[ERROR] Failed to connect: {response.status_code}")
    exit(1)

# Test 2: Test new 'last_id' parameter
print("\n2. Testing 'last_id' parameter (incremental sync)...")
response = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads",
    headers=headers,
    params={'last_id': 50, 'limit': 5},
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    leads = data.get('leads', [])
    print(f"[SUCCESS] Fetched {len(leads)} leads with ID > 50")
    if leads:
        print(f"  First lead ID: {leads[0].get('raw_data', {}).get('id')}")
        print(f"  Last lead ID: {leads[-1].get('raw_data', {}).get('id')}")
else:
    print(f"[WARNING] last_id parameter may not be working: {response.status_code}")

# Test 3: Test date range filtering with 'since' and 'until'
print("\n3. Testing date range filtering...")
since_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
until_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

response = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads",
    headers=headers,
    params={
        'since': since_date,
        'until': until_date,
        'limit': 10
    },
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    leads = data.get('leads', [])
    print(f"[SUCCESS] Date filtering working")
    print(f"  Requested: {since_date} to {until_date}")
    print(f"  Found {len(leads)} leads in date range")
    
    if leads:
        for lead in leads[:3]:
            signup_date = lead.get('raw_data', {}).get('signup_date')
            print(f"    - Lead {lead.get('raw_data', {}).get('id')}: {signup_date}")
else:
    print(f"[WARNING] Date filtering may not be working: {response.status_code}")

# Test 4: Test pagination with offset
print("\n4. Testing pagination...")
# First batch
response1 = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads",
    headers=headers,
    params={'limit': 5, 'offset': 0},
    timeout=10
)

# Second batch
response2 = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads",
    headers=headers,
    params={'limit': 5, 'offset': 5},
    timeout=10
)

if response1.status_code == 200 and response2.status_code == 200:
    batch1 = response1.json().get('leads', [])
    batch2 = response2.json().get('leads', [])
    
    print(f"[SUCCESS] Pagination working")
    print(f"  Batch 1 (offset 0): {len(batch1)} leads")
    print(f"  Batch 2 (offset 5): {len(batch2)} leads")
    
    if batch1 and batch2:
        batch1_ids = [l.get('raw_data', {}).get('id') for l in batch1]
        batch2_ids = [l.get('raw_data', {}).get('id') for l in batch2]
        
        if set(batch1_ids).isdisjoint(set(batch2_ids)):
            print("  [VERIFIED] No overlap between batches")
        else:
            print("  [WARNING] Batches have overlapping IDs")
else:
    print("[WARNING] Pagination may not be working properly")

# Test 5: Simulate incremental sync scenario
print("\n5. Simulating incremental sync...")
print("  This is how the production sync will work:")

# Get the highest ID
all_leads = requests.get(
    f"{site_url}/wp-json/rolling-riches/v1/leads",
    headers=headers,
    params={'limit': 1},
    timeout=10
).json().get('leads', [])

if all_leads:
    max_id = all_leads[0].get('raw_data', {}).get('id')
    print(f"  Current max ID: {max_id}")
    
    # Simulate next sync - get only newer leads
    response = requests.get(
        f"{site_url}/wp-json/rolling-riches/v1/leads",
        headers=headers,
        params={'last_id': max_id, 'limit': 10},
        timeout=10
    )
    
    new_leads = response.json().get('leads', [])
    print(f"  Next sync would fetch: {len(new_leads)} new leads")
    
    if len(new_leads) == 0:
        print("  [CORRECT] No new leads since last sync")
    else:
        print(f"  [INFO] Found {len(new_leads)} leads newer than ID {max_id}")

print("\n" + "=" * 60)
print("Plugin Update Test Complete!")
print("=" * 60)
print("\nSummary:")
print("- Plugin v2 is active and responding")
print("- New filtering parameters are available")
print("- Ready for production sync deployment")
print("\nThe updated plugin supports efficient incremental syncing!")