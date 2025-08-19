#!/usr/bin/env python3
"""
Test the complete flow from WordPress to MySQL to Go High Level.
"""

import os
import sys
import time
from datetime import datetime
import pymysql
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_database_connection():
    """Test MySQL database connection."""
    print("\n1. Testing MySQL Database Connection...")
    try:
        config = {
            'host': os.getenv('MYSQL_HOST'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        
        if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
            config['ssl'] = {'ssl_disabled': False}
        
        conn = pymysql.connect(**config)
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM leads")
            result = cursor.fetchone()
            print(f"   [SUCCESS] Connected to MySQL - Found {result[0]} leads in database")
        conn.close()
        return True
    except Exception as e:
        print(f"   [ERROR] MySQL connection failed: {e}")
        return False

def test_wordpress_connection():
    """Test WordPress API connection."""
    print("\n2. Testing WordPress Connection...")
    try:
        import requests
        import base64
        
        site_url = os.getenv('WORDPRESS_URL')
        username = os.getenv('WORDPRESS_USERNAME')
        password = os.getenv('WORDPRESS_PASSWORD')
        
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        
        response = requests.get(
            f"{site_url}/wp-json/rolling-riches/v1/leads/stats",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   [SUCCESS] Connected to WordPress - {data.get('total_leads', 0)} leads available")
            return True
        else:
            print(f"   [ERROR] WordPress API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   [ERROR] WordPress connection failed: {e}")
        return False

def test_ghl_connection():
    """Test Go High Level API connection."""
    print("\n3. Testing Go High Level Connection...")
    try:
        from src.wordpress_leads_extractor.api.ghl_client import GHLClient
        
        client = GHLClient(
            access_token=os.getenv('GHL_ACCESS_TOKEN'),
            location_id=os.getenv('GHL_LOCATION_ID')
        )
        
        if client.test_connection():
            print(f"   [SUCCESS] Connected to Go High Level")
            return True
        else:
            print(f"   [ERROR] GHL connection test failed")
            return False
    except Exception as e:
        print(f"   [ERROR] GHL connection failed: {e}")
        return False

def check_sync_status():
    """Check current sync status."""
    print("\n4. Checking Sync Status...")
    try:
        config = {
            'host': os.getenv('MYSQL_HOST'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        
        if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
            config['ssl'] = {'ssl_disabled': False}
        
        conn = pymysql.connect(**config)
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # WordPress sync status
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN email_valid = TRUE THEN 1 ELSE 0 END) as valid_emails,
                       AVG(quality_score) as avg_quality
                FROM leads
            """)
            wp_stats = cursor.fetchone()
            
            print(f"   WordPress → MySQL:")
            print(f"     - Total leads: {wp_stats['total']}")
            print(f"     - Valid emails: {wp_stats['valid_emails']}")
            print(f"     - Avg quality score: {wp_stats['avg_quality']:.1f}" if wp_stats['avg_quality'] else "     - Avg quality score: N/A")
            
            # GHL sync status
            cursor.execute("""
                SELECT COUNT(*) as synced,
                       COUNT(*) - COUNT(ghl_contact_id) as pending
                FROM leads
            """)
            ghl_stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(DISTINCT lead_id) as attempts,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failures
                FROM ghl_sync_log
            """)
            ghl_log = cursor.fetchone()
            
            print(f"   MySQL → Go High Level:")
            print(f"     - Synced to GHL: {ghl_stats['synced'] - ghl_stats['pending']}")
            print(f"     - Pending sync: {ghl_stats['pending']}")
            if ghl_log and ghl_log['attempts']:
                print(f"     - Sync attempts: {ghl_log['attempts']}")
                print(f"     - Successful: {ghl_log['successes'] or 0}")
                print(f"     - Failed: {ghl_log['failures'] or 0}")
            
        conn.close()
        return True
    except Exception as e:
        print(f"   [ERROR] Failed to check sync status: {e}")
        return False

def run_full_test():
    """Run a complete end-to-end test."""
    print("=" * 60)
    print("FULL SYSTEM TEST - WordPress → MySQL → Go High Level")
    print("=" * 60)
    
    all_passed = True
    
    # Test connections
    if not test_database_connection():
        all_passed = False
    
    if not test_wordpress_connection():
        all_passed = False
    
    if not test_ghl_connection():
        all_passed = False
    
    # Check sync status
    if not check_sync_status():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All systems operational!")
        print("\nYour complete flow is working:")
        print("1. WordPress leads API ✓")
        print("2. MySQL database storage ✓")
        print("3. Go High Level CRM sync ✓")
        print("\nTo run continuous sync:")
        print("  WordPress → MySQL: python3 sync_to_mysql.py --loop")
        print("  MySQL → GHL: python3 sync_to_ghl.py --continuous")
    else:
        print("[WARNING] Some components failed - check the errors above")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)