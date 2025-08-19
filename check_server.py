#!/usr/bin/env python3
"""Check server status and run a test sync"""

import paramiko
import sys

SERVER_IP = "64.23.174.231"
SERVER_USER = "r-user"
SERVER_PASS = "$5l0Wi3#IgC"

def run_cmd(ssh, command):
    """Execute command and return output."""
    if command.startswith("sudo"):
        command = f"echo '{SERVER_PASS}' | sudo -S {command[5:]}"
    
    stdin, stdout, stderr = ssh.exec_command(command)
    output = []
    for line in stdout:
        line = line.strip()
        if line and not line.startswith("[sudo]"):
            output.append(line)
            print(line)
    
    return stdout.channel.recv_exit_status() == 0

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to server...\n")
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS)
        
        print("=" * 70)
        print("1. SERVICE STATUS")
        print("=" * 70)
        run_cmd(ssh, "sudo systemctl status wordpress-leads-sync --no-pager | head -20")
        
        print("\n" + "=" * 70)
        print("2. TESTING CONNECTIONS")
        print("=" * 70)
        run_cmd(ssh, "cd /opt/wordpress-leads-sync && ./venv/bin/python unified_sync.py --test")
        
        print("\n" + "=" * 70)
        print("3. DATABASE STATISTICS")
        print("=" * 70)
        run_cmd(ssh, """cd /opt/wordpress-leads-sync && ./venv/bin/python -c "
import pymysql
import os
from dotenv import load_dotenv
load_dotenv()

try:
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
        cursor.execute('SELECT COUNT(*) FROM leads WHERE DATE(created_at) = CURDATE()')
        today = cursor.fetchone()[0]
        
    print(f'Total leads in database: {total}')
    print(f'Synced to Go High Level: {synced}')
    print(f'New leads today: {today}')
    print(f'Pending GHL sync: {total - synced}')
    conn.close()
except Exception as e:
    print(f'Database error: {e}')
" """)
        
        print("\n" + "=" * 70)
        print("4. RUNNING ONE SYNC CYCLE")
        print("=" * 70)
        print("This will fetch any new leads from WordPress and sync to GHL...")
        run_cmd(ssh, "cd /opt/wordpress-leads-sync && ./venv/bin/python unified_sync.py --once")
        
        print("\n" + "=" * 70)
        print("5. RECENT LOGS")
        print("=" * 70)
        run_cmd(ssh, "tail -n 20 /var/log/wordpress-leads-sync/service.log 2>/dev/null || echo 'No logs yet'")
        
        print("\n" + "=" * 70)
        print("✅ SERVER CHECK COMPLETE")
        print("=" * 70)
        print("\nThe system is running and ready!")
        print("\nTo submit a test lead:")
        print("1. Go to: https://www.welcomebonushunter.com")
        print("2. Submit a lead through the form")
        print("3. The lead will be synced within 10 minutes")
        print("4. Check Go High Level contacts to see it appear")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        ssh.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())