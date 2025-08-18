# =€ WordPress Leads to MySQL - Complete Deployment Guide

## Overview

This system syncs WordPress form submissions to a MySQL database with:
-  Automatic data cleaning and validation
-  Phone number standardization
-  Email validation
-  Duplicate detection
-  Quality scoring
-  Incremental sync (only new leads)
-  Automatic retry on failure
-  Comprehensive logging

## =Ë Prerequisites

Before deployment, you need:

1. **WordPress Site** with the Rolling Riches Leads API plugin installed
2. **MySQL Database** (5.7+ or 8.0+)
3. **Linux Server** (Ubuntu 20.04+ or similar)
4. **Python 3.8+** on the server
5. **Root/sudo access** for installation

## =' Step 1: Prepare MySQL Database

### Option A: Using MySQL Command Line

```bash
# Connect to your MySQL server
mysql -h your-mysql-host.com -u your_user -p

# Create database and tables
SOURCE mysql_schema.sql
```

### Option B: Using MySQL Workbench or phpMyAdmin

1. Copy contents of `mysql_schema.sql`
2. Execute in your MySQL client
3. Verify tables were created:
   - `leads` - Main table for cleaned data
   - `sync_log` - Tracks sync history
   - `email_blacklist` - Filters spam emails

## =æ Step 2: Prepare Files for Deployment

### Required Files

Ensure you have these files ready:
- `sync_to_mysql.py` - Main sync script
- `mysql_schema.sql` - Database schema
- `requirements-prod.txt` - Python dependencies
- `deploy.sh` - Deployment script
- `leads-sync.service` - Systemd service file
- `.env.production` - Configuration template

### Update Configuration

Edit `.env.production` with your MySQL credentials:

```env
# MySQL Configuration (REQUIRED)
MYSQL_HOST=your-mysql-cluster.amazonaws.com
MYSQL_PORT=3306
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_secure_password
MYSQL_DATABASE=rolling_riches_leads

# WordPress (already configured)
WORDPRESS_URL=https://www.welcomebonushunter.com
WORDPRESS_USERNAME=admin_6797
WORDPRESS_PASSWORD=H2it UYw9 O9hh QpD5 4LMr QU0e
```

## =¥ Step 3: Deploy to Server

### Option A: Automated Deployment

1. **Upload files to server:**
```bash
# Create archive
tar -czf leads-sync.tar.gz sync_to_mysql.py mysql_schema.sql \
    requirements-prod.txt deploy.sh leads-sync.service .env.production

# Upload to server
scp leads-sync.tar.gz user@your-server:/tmp/
```

2. **SSH to server and run deployment:**
```bash
ssh user@your-server
cd /tmp
tar -xzf leads-sync.tar.gz
sudo bash deploy.sh
```

### Option B: Manual Deployment

1. **SSH to your server:**
```bash
ssh user@your-server
```

2. **Create application directory:**
```bash
sudo mkdir -p /opt/rolling-riches-leads
cd /opt/rolling-riches-leads
```

3. **Upload files** (from local machine):
```bash
scp sync_to_mysql.py user@server:/opt/rolling-riches-leads/
scp requirements-prod.txt user@server:/opt/rolling-riches-leads/
scp .env.production user@server:/opt/rolling-riches-leads/.env
```

4. **Install dependencies:**
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv mysql-client

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-prod.txt
```

5. **Set up systemd service:**
```bash
sudo cp leads-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable leads-sync
sudo systemctl start leads-sync
```

## ™ Step 4: Configure Sync Settings

### Sync Frequency

Default: Every 5 minutes. To change:

```bash
# Edit service file
sudo nano /etc/systemd/system/leads-sync.service

# Change the --interval parameter (in seconds)
ExecStart=/opt/rolling-riches-leads/venv/bin/python sync_to_mysql.py --loop --interval 60

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart leads-sync
```

### Data Cleaning Rules

The system automatically:
- Validates email format
- Removes duplicate emails
- Standardizes phone numbers to E.164 format
- Calculates quality scores (0-100)
- Filters test/spam emails

## =Ê Step 5: Verify Deployment

### Check Service Status

```bash
sudo systemctl status leads-sync
```

Should show: `Active: active (running)`

### View Logs

```bash
# Real-time logs
sudo journalctl -u leads-sync -f

# Last 100 lines
sudo tail -100 /var/log/leads-sync.log
```

### Test Manual Sync

```bash
cd /opt/rolling-riches-leads
source venv/bin/activate
python sync_to_mysql.py --full  # Full sync
```

### Verify in MySQL

```sql
-- Check lead count
SELECT COUNT(*) FROM leads;

-- View recent leads
SELECT email, signup_date, quality_score 
FROM leads 
ORDER BY signup_date DESC 
LIMIT 10;

-- Check sync history
SELECT * FROM sync_log 
ORDER BY sync_started_at DESC 
LIMIT 5;

-- Daily statistics
SELECT * FROM daily_summary;
```

## = Step 6: Monitoring

### Set Up Alerts

Add email alerts for failures:

```bash
# Edit .env file
sudo nano /opt/rolling-riches-leads/.env

# Add SMTP settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL=admin@yourcompany.com
```

### Health Check Script

Create `/usr/local/bin/check-leads`:

```bash
#!/bin/bash
if ! systemctl is-active --quiet leads-sync; then
    echo "Lead sync down at $(date)" | mail -s "ALERT: Lead Sync Failed" admin@example.com
    systemctl restart leads-sync
fi
```

Add to crontab:
```bash
*/5 * * * * /usr/local/bin/check-leads
```

## =à Maintenance

### Common Commands

```bash
# Stop service
sudo systemctl stop leads-sync

# Start service
sudo systemctl start leads-sync

# Restart service
sudo systemctl restart leads-sync

# View full logs
sudo journalctl -u leads-sync

# Run one-time full sync
cd /opt/rolling-riches-leads
source venv/bin/activate
python sync_to_mysql.py --full
```

### Database Maintenance

```sql
-- Clean old sync logs (keep 30 days)
DELETE FROM sync_log 
WHERE sync_started_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- Find duplicate emails
SELECT email, COUNT(*) as count 
FROM leads 
GROUP BY email 
HAVING count > 1;

-- Update quality scores
UPDATE leads 
SET quality_score = calculate_quality_score(email, phone, signup_source)
WHERE quality_score IS NULL;
```

## =È Performance Optimization

### For Large Datasets (10k+ leads)

1. **Increase batch size** in sync script:
```python
# Edit sync_to_mysql.py
leads = self.wp_sync.fetch_leads(limit=1000)  # Increase from 500
```

2. **Add MySQL indexes** if queries are slow:
```sql
ALTER TABLE leads ADD INDEX idx_signup_month (YEAR(signup_date), MONTH(signup_date));
```

3. **Enable MySQL query cache**:
```sql
SET GLOBAL query_cache_size = 67108864;  # 64MB
SET GLOBAL query_cache_type = 1;
```

## = Security Considerations

1. **Secure .env file:**
```bash
sudo chmod 600 /opt/rolling-riches-leads/.env
sudo chown www-data:www-data /opt/rolling-riches-leads/.env
```

2. **Use SSL for MySQL:**
```python
# Add to connection params in sync_to_mysql.py
'ssl': {'ca': '/path/to/ca.pem'}
```

3. **Rotate WordPress Application Password** monthly

4. **Limit MySQL user permissions:**
```sql
GRANT SELECT, INSERT, UPDATE ON rolling_riches_leads.* TO 'sync_user'@'%';
```

## S Troubleshooting

### Service Won't Start
```bash
# Check for errors
sudo journalctl -u leads-sync -n 50

# Verify Python path
which python3

# Test script directly
cd /opt/rolling-riches-leads
source venv/bin/activate
python sync_to_mysql.py --full
```

### MySQL Connection Failed
- Verify credentials in `.env`
- Check firewall allows connection
- Test connection: `mysql -h host -u user -p`

### No Leads Syncing
- Verify WordPress plugin is active
- Check API endpoint: `curl https://site.com/wp-json/rolling-riches/v1/leads/stats`
- Review WordPress application password

## =Þ Need Help?

If you provide your server credentials, I can:
1. SSH into your server
2. Run the deployment automatically
3. Configure monitoring
4. Test the complete system

Just provide:
- SSH access (host, username, password/key)
- MySQL credentials
- Preferred installation directory

The system is ready for production deployment! =€