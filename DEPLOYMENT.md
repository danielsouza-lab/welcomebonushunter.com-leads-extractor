# 🚀 Deployment Guide - WordPress Leads Sync

This guide covers deploying the WordPress → MySQL → Go High Level sync system on Ubuntu Server.

## 📋 Prerequisites

- Ubuntu 20.04+ server
- Root or sudo access
- GitHub repository access
- Credentials for:
  - WordPress site with API plugin
  - MySQL database (DigitalOcean or other)
  - Go High Level API

## 🔧 Quick Deployment

### 1. Connect to your Ubuntu server

```bash
ssh your-user@your-server-ip
```

### 2. Download and run deployment script

```bash
# Download the deployment script
wget https://raw.githubusercontent.com/danielsouza-lab/welcomebonushunter.com-leads-extractor/main/deploy_ubuntu.sh

# Make it executable
chmod +x deploy_ubuntu.sh

# Run as root
sudo ./deploy_ubuntu.sh
```

### 3. Configure credentials

After deployment, edit the `.env` file with your credentials:

```bash
sudo nano /opt/wordpress-leads-sync/.env
```

Add your credentials:

```env
# WordPress Configuration
WORDPRESS_URL=https://www.welcomebonushunter.com
WORDPRESS_USERNAME=your_username
WORDPRESS_PASSWORD=your_app_password

# MySQL Database Configuration  
MYSQL_HOST=your-db-host.ondigitalocean.com
MYSQL_PORT=25060
MYSQL_USER=doadmin
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=welcomebonushunter
MYSQL_SSL=true

# Go High Level Configuration
GHL_ACCESS_TOKEN=your_ghl_token
GHL_LOCATION_ID=your_location_id

# Retry Configuration (optional)
RETRY_HOUR=23  # Hour for daily retry (0-23, default 23 = 11 PM)
```

### 4. Test connections

```bash
wp-sync test
```

### 5. Start the service

```bash
wp-sync start
```

## 📊 Management Commands

Once deployed, use the `wp-sync` command to manage the service:

| Command | Description |
|---------|-------------|
| `wp-sync start` | Start the sync service |
| `wp-sync stop` | Stop the sync service |
| `wp-sync restart` | Restart the service |
| `wp-sync status` | Check service status |
| `wp-sync logs` | View live logs |
| `wp-sync errors` | View error logs |
| `wp-sync monitor` | Show monitoring dashboard |
| `wp-sync update` | Update from GitHub |
| `wp-sync test` | Test all connections |
| `wp-sync retry` | Manually retry failed GHL syncs |

## 🔄 How It Works

1. **Every 10 minutes**, the service:
   - Fetches new leads from WordPress (last 11 minutes)
   - Saves them to MySQL with data cleaning
   - Syncs new leads to Go High Level
   - Logs all operations

2. **Every day at 11 PM**, the service:
   - Identifies all failed GHL syncs from the day
   - Retries them in order of quality score
   - Logs retry results

3. **Automatic features**:
   - Duplicate detection
   - Quality scoring (0-100)
   - Email/phone validation
   - Automatic retry on failures
   - Daily retry for persistent failures
   - Log rotation (30 days)

## 📁 File Locations

- **Application**: `/opt/wordpress-leads-sync/`
- **Logs**: `/var/log/wordpress-leads-sync/`
- **Service**: `/etc/systemd/system/wordpress-leads-sync.service`
- **Config**: `/opt/wordpress-leads-sync/.env`

## 🔍 Monitoring

### View live logs
```bash
wp-sync logs
```

### Check service status
```bash
wp-sync status
```

### View monitoring dashboard
```bash
wp-sync monitor
```

### Check database stats
```bash
mysql -h your-host -u your-user -p welcomebonushunter -e "
SELECT 
    (SELECT COUNT(*) FROM leads) as total_leads,
    (SELECT COUNT(*) FROM leads WHERE ghl_synced = TRUE) as synced_to_ghl,
    (SELECT COUNT(*) FROM leads WHERE DATE(created_at) = CURDATE()) as leads_today;
"
```

## 🔄 Updating

### Manual update from GitHub
```bash
wp-sync update
```

### Automatic updates via GitHub Actions

1. Set up GitHub secrets in your repository:
   - `SERVER_HOST`: Your server IP
   - `SERVER_USER`: SSH username (usually `root`)
   - `SERVER_SSH_KEY`: Your private SSH key
   - `SERVER_PORT`: SSH port (usually `22`)

2. Push to main branch to auto-deploy:
```bash
git push origin main
```

## 🛠️ Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u wordpress-leads-sync -n 50

# Test connections
wp-sync test

# Check permissions
ls -la /opt/wordpress-leads-sync/
```

### No leads syncing
```bash
# Check WordPress API
curl -u username:password https://your-site.com/wp-json/rolling-riches/v1/leads/stats

# Check MySQL connection
mysql -h your-host -u your-user -p -e "SELECT 1"

# Check GHL token
python3 -c "
from src.wordpress_leads_extractor.api.ghl_client import GHLClient
client = GHLClient('your_token', 'your_location_id')
print(client.test_connection())
"
```

### High memory usage
```bash
# Restart service
wp-sync restart

# Check memory
free -h
ps aux | grep python
```

## 🔒 Security

1. **Credentials**: Stored in `.env` with 600 permissions
2. **Service**: Runs as `www-data` user (non-root)
3. **Logs**: Rotated daily, kept for 30 days
4. **Network**: Uses SSL for MySQL and HTTPS for APIs

## 📈 Performance

- **Sync interval**: Every 10 minutes
- **Processing time**: ~1-2 seconds per lead
- **Memory usage**: ~50-100MB
- **CPU usage**: <5% average

## 🆘 Support

### View all logs
```bash
# Service logs
tail -n 100 /var/log/wordpress-leads-sync/service.log

# Error logs
tail -n 100 /var/log/wordpress-leads-sync/error.log

# System logs
sudo journalctl -u wordpress-leads-sync --since "1 hour ago"
```

### Database queries
```bash
# Check sync history
mysql -h your-host -u your-user -p welcomebonushunter -e "
SELECT * FROM sync_log ORDER BY id DESC LIMIT 10;
"

# Check GHL sync status
mysql -h your-host -u your-user -p welcomebonushunter -e "
SELECT * FROM ghl_sync_status LIMIT 10;
"
```

## 📝 Notes

- The service automatically starts on server boot
- Logs are rotated daily to prevent disk space issues
- Failed GHL syncs are logged and can be retried
- The system handles duplicates automatically
- Quality scores help prioritize high-value leads