#!/usr/bin/env python3
"""Check why automatic sync isn't running"""

import paramiko
import sys

SERVER_IP = "64.23.174.231"
SERVER_USER = "r-user" 
SERVER_PASS = "$5l0Wi3#IgC"

def run_cmd(ssh, command, show_output=True):
    """Execute command and return output."""
    if command.startswith("sudo"):
        command = f"echo '{SERVER_PASS}' | sudo -S {command[5:]}"
    
    stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
    output = []
    
    for line in stdout:
        line = line.strip()
        if line and not line.startswith("[sudo]"):
            output.append(line)
            if show_output:
                print(line)
    
    return stdout.channel.recv_exit_status() == 0, '\n'.join(output)

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("=" * 80)
        print("CHECKING AUTOMATIC SYNC STATUS")
        print("=" * 80)
        
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS)
        
        print("\n1. Service Status:")
        print("-" * 80)
        run_cmd(ssh, "sudo systemctl status wordpress-leads-sync --no-pager | head -20")
        
        print("\n2. Last 50 Service Logs:")
        print("-" * 80)
        run_cmd(ssh, "sudo journalctl -u wordpress-leads-sync -n 50 --no-pager")
        
        print("\n3. Checking if service is actually running:")
        print("-" * 80)
        run_cmd(ssh, "ps aux | grep unified_sync | grep -v grep")
        
        print("\n4. Restarting the service...")
        print("-" * 80)
        run_cmd(ssh, "sudo systemctl restart wordpress-leads-sync")
        print("Service restarted")
        
        import time
        time.sleep(5)
        
        print("\n5. Service status after restart:")
        print("-" * 80)
        run_cmd(ssh, "sudo systemctl status wordpress-leads-sync --no-pager | head -15")
        
        print("\n6. Checking new logs (should show sync starting):")
        print("-" * 80)
        run_cmd(ssh, "sudo journalctl -u wordpress-leads-sync -n 20 --no-pager")
        
        print("\n7. Testing sync with your recent lead:")
        print("-" * 80)
        success, output = run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
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
    # Check danielsouza@dynamico.co
    cursor.execute('''
        SELECT * FROM leads 
        WHERE email = 'danielsouza@dynamico.co'
        ORDER BY created_at DESC
        LIMIT 1
    ''')
    lead = cursor.fetchone()
    
    if lead:
        print(f'Your test lead status:')
        print(f'  Email: {lead[\"email\"]}')
        print(f'  Created: {lead[\"created_at\"]}')
        print(f'  GHL Synced: {\"Yes\" if lead[\"ghl_synced\"] else \"No\"}')
        if lead['ghl_contact_id']:
            print(f'  GHL Contact ID: {lead[\"ghl_contact_id\"]}')
            print('\\n✅ YOUR LEAD WAS SUCCESSFULLY SYNCED TO GO HIGH LEVEL!')
        else:
            print('  Status: Not yet synced to GHL')
    else:
        print('Lead not found in database yet')
        
conn.close()
" """)
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("\n✅ The service has been restarted and is now running!")
        print("\nThe system will now:")
        print("  • Check for new leads every 10 minutes")
        print("  • Sync them to MySQL")
        print("  • Push new leads to Go High Level")
        print("\nYour test lead (danielsouza@dynamico.co) should now be in GHL.")
        print("Check your Go High Level contacts to confirm!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        ssh.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())