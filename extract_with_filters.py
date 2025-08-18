#!/usr/bin/env python3
"""Extract WordPress leads with various filters and display results."""

import os
import requests
import base64
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

# Get credentials
site_url = os.getenv('WORDPRESS_URL')
username = os.getenv('WORDPRESS_USERNAME')
password = os.getenv('WORDPRESS_PASSWORD')

# Setup authentication
credentials = base64.b64encode(f"{username}:{password}".encode()).decode('ascii')
headers = {'Authorization': f'Basic {credentials}'}

print("=" * 80)
print("WORDPRESS LEADS EXTRACTION WITH FILTERS")
print("=" * 80)

def fetch_leads(params=None):
    """Fetch leads with given parameters."""
    response = requests.get(
        f"{site_url}/wp-json/rolling-riches/v1/leads",
        headers=headers,
        params=params or {},
        timeout=10
    )
    if response.status_code == 200:
        return response.json().get('leads', [])
    return []

def display_leads(leads, title):
    """Display leads in a formatted table."""
    print(f"\n{title}")
    print("-" * 80)
    
    if not leads:
        print("No leads found with this filter.")
        return
    
    print(f"Found {len(leads)} leads:\n")
    print(f"{'ID':<5} {'Email':<35} {'Phone':<15} {'Date':<20} {'Source':<10}")
    print("-" * 80)
    
    for lead in leads:
        raw = lead.get('raw_data', {})
        lead_id = str(raw.get('id', 'N/A'))
        email = raw.get('email', 'N/A')[:33]
        phone = raw.get('phone', 'N/A')[:13] if raw.get('phone') else 'N/A'
        date = raw.get('signup_date', 'N/A')
        source = raw.get('source', 'N/A')
        
        print(f"{lead_id:<5} {email:<35} {phone:<15} {date:<20} {source:<10}")

# 1. Get ALL leads
print("\n1. FETCHING ALL LEADS")
all_leads = fetch_leads({'limit': 100})
display_leads(all_leads, "ALL LEADS IN DATABASE")

# Save to JSON
with open('all_leads.json', 'w') as f:
    json.dump(all_leads, f, indent=2, default=str)
print(f"\n[SAVED] All {len(all_leads)} leads to 'all_leads.json'")

# 2. Get leads from last 7 days
print("\n" + "=" * 80)
print("\n2. LEADS FROM LAST 7 DAYS")
seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
recent_leads = fetch_leads({'since': seven_days_ago})
display_leads(recent_leads, f"LEADS SINCE {seven_days_ago}")

# 3. Get leads from specific date range
print("\n" + "=" * 80)
print("\n3. LEADS FROM SPECIFIC DATE RANGE (Aug 12-14, 2025)")
date_range_leads = fetch_leads({
    'since': '2025-08-12 00:00:00',
    'until': '2025-08-14 23:59:59'
})
display_leads(date_range_leads, "LEADS FROM AUG 12-14, 2025")

# 4. Get latest 5 leads
print("\n" + "=" * 80)
print("\n4. LATEST 5 LEADS")
latest_leads = fetch_leads({'limit': 5})
display_leads(latest_leads, "5 MOST RECENT LEADS")

# 5. Get leads after specific ID (incremental sync demo)
print("\n" + "=" * 80)
print("\n5. INCREMENTAL SYNC DEMO (Leads with ID > 54)")
incremental_leads = fetch_leads({'last_id': 54, 'limit': 10})
display_leads(incremental_leads, "LEADS WITH ID > 54")

# 6. Analyze lead quality
print("\n" + "=" * 80)
print("\n6. LEAD QUALITY ANALYSIS")
print("-" * 80)

with_phone = 0
without_phone = 0
email_domains = defaultdict(int)
sources = defaultdict(int)
dates = defaultdict(int)

for lead in all_leads:
    raw = lead.get('raw_data', {})
    
    # Phone analysis
    if raw.get('phone'):
        with_phone += 1
    else:
        without_phone += 1
    
    # Email domain analysis
    email = raw.get('email', '')
    if '@' in email:
        domain = email.split('@')[1].lower()
        email_domains[domain] += 1
    
    # Source analysis
    source = raw.get('source', 'unknown')
    sources[source] += 1
    
    # Date analysis
    signup_date = raw.get('signup_date', '')
    if signup_date:
        date_only = signup_date.split(' ')[0]
        dates[date_only] += 1

print(f"\nSTATISTICS:")
print(f"  Total Leads: {len(all_leads)}")
print(f"  With Phone: {with_phone} ({with_phone*100//len(all_leads) if all_leads else 0}%)")
print(f"  Without Phone: {without_phone} ({without_phone*100//len(all_leads) if all_leads else 0}%)")

print(f"\nTOP EMAIL DOMAINS:")
for domain, count in sorted(email_domains.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {domain}: {count} leads")

print(f"\nLEAD SOURCES:")
for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
    print(f"  {source}: {count} leads")

print(f"\nLEADS BY DATE:")
for date, count in sorted(dates.items(), reverse=True)[:5]:
    print(f"  {date}: {count} leads")

# 7. Export cleaned data
print("\n" + "=" * 80)
print("\n7. EXPORTING CLEANED DATA")
print("-" * 80)

cleaned_leads = []
for lead in all_leads:
    raw = lead.get('raw_data', {})
    
    # Clean and structure the data
    cleaned = {
        'id': raw.get('id'),
        'email': raw.get('email', '').strip().lower(),
        'phone': raw.get('phone', '').strip() if raw.get('phone') else None,
        'signup_date': raw.get('signup_date'),
        'source': raw.get('source', 'unknown'),
        'email_domain': raw.get('email', '').split('@')[1].lower() if '@' in raw.get('email', '') else None,
        'has_phone': bool(raw.get('phone')),
        'quality_score': 50  # Base score
    }
    
    # Calculate quality score
    score = 50
    if cleaned['email'] and '@' in cleaned['email']:
        score += 20
    if cleaned['has_phone']:
        score += 15
    if cleaned['email_domain'] and cleaned['email_domain'] not in ['gmail.com', 'yahoo.com', 'hotmail.com']:
        score += 10
    cleaned['quality_score'] = min(score, 100)
    
    cleaned_leads.append(cleaned)

# Save cleaned data
with open('cleaned_leads.json', 'w') as f:
    json.dump(cleaned_leads, f, indent=2, default=str)

# Save as CSV for easy import
import csv
with open('cleaned_leads.csv', 'w', newline='') as f:
    if cleaned_leads:
        writer = csv.DictWriter(f, fieldnames=cleaned_leads[0].keys())
        writer.writeheader()
        writer.writerows(cleaned_leads)

print(f"[EXPORTED] {len(cleaned_leads)} cleaned leads to:")
print(f"  - cleaned_leads.json (for programming)")
print(f"  - cleaned_leads.csv (for Excel/spreadsheets)")

print("\n" + "=" * 80)
print("EXTRACTION COMPLETE!")
print("=" * 80)
print(f"\nTotal leads extracted: {len(all_leads)}")
print("Files created:")
print("  - all_leads.json - Raw data from WordPress")
print("  - cleaned_leads.json - Cleaned and structured data")
print("  - cleaned_leads.csv - For spreadsheet import")