#!/usr/bin/env python3
"""Debug why leads are not syncing to GHL"""

import paramiko
import sys
from datetime import datetime

SERVER_IP = "64.23.174.231"
SERVER_USER = "r-user" 
SERVER_PASS = "$5l0Wi3#IgC"

def run_cmd(ssh, command, show_output=True):
    """Execute command and return output."""
    if command.startswith("sudo"):
        command = f"echo '{SERVER_PASS}' | sudo -S {command[5:]}"
    
    stdin, stdout, stderr = ssh.exec_command(command, timeout=60)
    output = []
    errors = []
    
    for line in stdout:
        line = line.strip()
        if line and not line.startswith("[sudo]"):
            output.append(line)
            if show_output:
                print(line)
    
    for line in stderr:
        line = line.strip()
        if line and "[sudo]" not in line:
            errors.append(line)
    
    return stdout.channel.recv_exit_status() == 0, '\n'.join(output), '\n'.join(errors)

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("=" * 80)
        print("DEBUGGING SYNC ISSUE")
        print("=" * 80)
        
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS)
        
        print("\n1. Checking for new WordPress leads...")
        print("-" * 80)
        success, output, errors = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
import os
import sys
import requests
import base64
from datetime import datetime, timedelta
sys.path.insert(0, '/opt/wordpress-leads-sync')
from dotenv import load_dotenv
load_dotenv()

# WordPress credentials
url = os.getenv('WORDPRESS_URL')
user = os.getenv('WORDPRESS_USERNAME')
pwd = os.getenv('WORDPRESS_PASSWORD')

# Get leads from last hour
since = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
print(f'Fetching leads since: {since}')

credentials = base64.b64encode(f'{user}:{pwd}'.encode()).decode()
headers = {'Authorization': f'Basic {credentials}'}

params = {
    'since': since,
    'limit': 100
}

try:
    response = requests.get(
        f'{url}/wp-json/rolling-riches/v1/leads',
        headers=headers,
        params=params,
        timeout=30
    )
    
    print(f'API Response Status: {response.status_code}')
    
    if response.status_code == 200:
        data = response.json()
        leads = data.get('leads', [])
        print(f'Found {len(leads)} new leads in WordPress')
        
        if leads:
            print('\\nRecent leads:')
            for lead in leads[:5]:  # Show first 5
                print(f\"  - {lead.get('email', 'no-email')} at {lead.get('signup_date', 'unknown')}\")
    else:
        print(f'API Error: {response.text[:200]}')
        
except Exception as e:
    print(f'Error fetching from WordPress: {e}')
" """)
        
        print("\n2. Checking MySQL for recent leads...")
        print("-" * 80)
        success, output, errors = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
import pymysql
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST'),
    port=int(os.getenv('MYSQL_PORT')),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE'),
    ssl={'ssl_disabled': False}
)

with conn.cursor(pymysql.cursors.DictCursor) as cursor:
    # Get leads from last hour
    cursor.execute('''
        SELECT id, email, created_at, ghl_synced, ghl_contact_id
        FROM leads 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
        ORDER BY created_at DESC
        LIMIT 10
    ''')
    recent_leads = cursor.fetchall()
    
    print(f'Found {len(recent_leads)} leads in MySQL from last hour')
    
    if recent_leads:
        print('\\nRecent leads in database:')
        for lead in recent_leads:
            sync_status = '✓ Synced' if lead['ghl_synced'] else '✗ Not synced'
            print(f\"  - {lead['email']} at {lead['created_at']} - {sync_status}\")
            if lead['ghl_contact_id']:
                print(f\"    GHL ID: {lead['ghl_contact_id']}\")
    
    # Check unsynced leads
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE ghl_synced = FALSE')
    unsynced = cursor.fetchone()['count']
    print(f'\\nTotal unsynced leads: {unsynced}')
    
conn.close()
" """)
        
        print("\n3. Checking sync log for recent attempts...")
        print("-" * 80)
        success, output, errors = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
import pymysql
import os
from dotenv import load_dotenv
load_dotenv()

conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST'),
    port=int(os.getenv('MYSQL_PORT')),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE'),
    ssl={'ssl_disabled': False}
)

with conn.cursor(pymysql.cursors.DictCursor) as cursor:
    # Check sync log
    cursor.execute('''
        SELECT * FROM sync_log 
        ORDER BY id DESC 
        LIMIT 5
    ''')
    syncs = cursor.fetchall()
    
    if syncs:
        print('Recent sync attempts:')
        for sync in syncs:
            print(f\"  - {sync['sync_type']} at {sync.get('sync_completed_at', 'in progress')}\")
            print(f\"    Records: {sync.get('total_records', 0)}, New: {sync.get('new_records', 0)}\")
    else:
        print('No sync attempts found')
    
    # Check GHL sync log
    cursor.execute('''
        SELECT * FROM ghl_sync_log 
        ORDER BY id DESC 
        LIMIT 5
    ''')
    ghl_syncs = cursor.fetchall()
    
    if ghl_syncs:
        print('\\nRecent GHL sync attempts:')
        for sync in ghl_syncs:
            print(f\"  - {sync['email']} - Status: {sync['status']}\")
            if sync['error_message']:
                print(f\"    Error: {sync['error_message']}\")
    else:
        print('\\nNo GHL sync attempts found')
        
conn.close()
" """)
        
        print("\n4. Running a manual sync NOW...")
        print("-" * 80)
        success, output, errors = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python unified_sync.py --once 2>&1""")
        
        if errors:
            print(f"Errors during sync: {errors}")
        
        print("\n5. Checking service logs for errors...")
        print("-" * 80)
        run_cmd(ssh, "sudo journalctl -u wordpress-leads-sync -n 30 --no-pager | grep -E 'ERROR|Failed|Exception|Traceback' || echo 'No errors in service logs'")
        
        print("\n6. Testing direct GHL sync for unsynced leads...")
        print("-" * 80)
        success, output, errors = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
import os
import sys
sys.path.insert(0, '/opt/wordpress-leads-sync')
from dotenv import load_dotenv
load_dotenv()

import pymysql

# Get one unsynced lead
conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST'),
    port=int(os.getenv('MYSQL_PORT')),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE'),
    ssl={'ssl_disabled': False}
)

with conn.cursor(pymysql.cursors.DictCursor) as cursor:
    cursor.execute('''
        SELECT * FROM leads 
        WHERE ghl_synced = FALSE 
        ORDER BY created_at DESC
        LIMIT 1
    ''')
    lead = cursor.fetchone()
    
    if lead:
        print(f'Testing sync for: {lead[\"email\"]}')
        
        # Try to sync this lead
        from unified_sync import UnifiedSyncService
        service = UnifiedSyncService()
        
        success = service.sync_lead_to_ghl(lead['id'])
        
        if success:
            print(f'✓ Successfully synced {lead[\"email\"]} to GHL!')
        else:
            print(f'✗ Failed to sync {lead[\"email\"]}')
            
            # Check error log
            cursor.execute('''
                SELECT error_message, response_body 
                FROM ghl_sync_log 
                WHERE lead_id = %s 
                ORDER BY id DESC 
                LIMIT 1
            ''', (lead['id'],))
            error = cursor.fetchone()
            if error:
                print(f'Error: {error[\"error_message\"]}')
                print(f'Response: {error[\"response_body\"]}')
    else:
        print('No unsynced leads found')
        
conn.close()
" """)
        
        print("\n" + "=" * 80)
        print("DIAGNOSIS SUMMARY")
        print("=" * 80)
        
        print("\n📋 Next Steps:")
        print("1. Check if your test lead appears in the output above")
        print("2. If the lead is in WordPress but not MySQL, the WordPress→MySQL sync failed")
        print("3. If the lead is in MySQL but not synced, the MySQL→GHL sync failed")
        print("4. Check for any error messages above")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        ssh.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())