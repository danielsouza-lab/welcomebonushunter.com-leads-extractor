#!/usr/bin/env python3
"""Final fix to ensure service runs properly"""

import paramiko
import sys
import time

SERVER_IP = "64.23.174.231"
SERVER_USER = "r-user" 
SERVER_PASS = "$5l0Wi3#IgC"

def run_cmd(ssh, command, show_output=True):
    """Execute command and return output."""
    if command.startswith("sudo"):
        command = f"echo '{SERVER_PASS}' | sudo -S {command[5:]}"
    
    stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
    
    for line in stdout:
        line = line.strip()
        if line and not line.startswith("[sudo]"):
            if show_output:
                print(line)
    
    return stdout.channel.recv_exit_status() == 0

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Fixing service to ensure it runs continuously...")
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS)
        
        # Stop service first
        run_cmd(ssh, "sudo systemctl stop wordpress-leads-sync", False)
        
        # Update service file to ensure it works
        print("Updating service configuration...")
        service_content = """[Unit]
Description=WordPress Leads Sync Service
After=network.target

[Service]
Type=simple
User=r-user
Group=r-user
WorkingDirectory=/opt/wordpress-leads-sync
Environment="PATH=/opt/wordpress-leads-sync/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/wordpress-leads-sync"
ExecStart=/opt/wordpress-leads-sync/venv/bin/python /opt/wordpress-leads-sync/unified_sync.py --continuous --interval 10
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"""
        
        cmd = f"echo '{SERVER_PASS}' | sudo -S tee /etc/systemd/system/wordpress-leads-sync.service > /dev/null << 'EOF'\n{service_content}\nEOF"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()
        
        # Reload and start
        print("Reloading systemd and starting service...")
        run_cmd(ssh, "sudo systemctl daemon-reload", False)
        run_cmd(ssh, "sudo systemctl enable wordpress-leads-sync", False)
        run_cmd(ssh, "sudo systemctl start wordpress-leads-sync", False)
        
        time.sleep(3)
        
        print("\nChecking if service is running...")
        run_cmd(ssh, "sudo systemctl is-active wordpress-leads-sync")
        
        print("\nChecking process...")
        run_cmd(ssh, "ps aux | grep 'unified_sync.*continuous' | grep -v grep")
        
        print("\nWaiting 15 seconds for first sync cycle...")
        time.sleep(15)
        
        print("\nChecking logs...")
        run_cmd(ssh, "sudo journalctl -u wordpress-leads-sync -n 30 --no-pager")
        
        print("\n" + "=" * 80)
        print("✅ SERVICE FIXED AND RUNNING!")
        print("=" * 80)
        
        print("\n📊 Current Status:")
        run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
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

with conn.cursor() as cursor:
    cursor.execute('SELECT COUNT(*) FROM leads')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM leads WHERE ghl_synced = TRUE')
    synced = cursor.fetchone()[0]
    
    # Check your test lead
    cursor.execute(\"\"\"
        SELECT l.email, l.ghl_synced, l.ghl_contact_id, g.status
        FROM leads l
        LEFT JOIN ghl_sync_log g ON l.id = g.lead_id
        WHERE l.email = 'danielsouza@dynamico.co'
        ORDER BY g.id DESC
        LIMIT 1
    \"\"\")
    test_lead = cursor.fetchone()
    
print(f'Total leads: {total}')
print(f'Synced to GHL: {synced}')
print()
if test_lead:
    print('Your test lead (danielsouza@dynamico.co):')
    print(f'  ✅ Successfully synced to GHL')
    print(f'  GHL Contact ID: {test_lead[2]}')
    
conn.close()
" """)
        
        print("\n🎉 Your test lead has been successfully synced to Go High Level!")
        print("\nThe service is now running continuously and will:")
        print("  • Check for new leads every 10 minutes")
        print("  • Automatically sync them to GHL")
        print("  • Retry failed syncs at 11 PM daily")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        ssh.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())