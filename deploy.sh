#!/bin/bash

# Rolling Riches Lead Sync Deployment Script
# Run this on your server to deploy the sync service

set -e

echo "==========================================="
echo "Rolling Riches Lead Sync Deployment"
echo "==========================================="

# Configuration
APP_DIR="/opt/rolling-riches-leads"
SERVICE_NAME="leads-sync"
USER="www-data"  # Change to your preferred user

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "1. Creating application directory..."
mkdir -p $APP_DIR
cd $APP_DIR

echo "2. Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv mysql-client

echo "3. Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "4. Installing Python packages..."
pip install --upgrade pip
pip install -r requirements-prod.txt

echo "5. Setting up MySQL database..."
read -p "Enter MySQL host: " mysql_host
read -p "Enter MySQL port [3306]: " mysql_port
mysql_port=${mysql_port:-3306}
read -p "Enter MySQL username: " mysql_user
read -sp "Enter MySQL password: " mysql_password
echo
read -p "Enter database name [rolling_riches_leads]: " mysql_db
mysql_db=${mysql_db:-rolling_riches_leads}

# Create .env file
cat > .env << EOF
# WordPress Configuration
WORDPRESS_URL=https://www.welcomebonushunter.com
WORDPRESS_USERNAME=admin_6797
WORDPRESS_PASSWORD=H2it UYw9 O9hh QpD5 4LMr QU0e

# MySQL Configuration
MYSQL_HOST=$mysql_host
MYSQL_PORT=$mysql_port
MYSQL_USER=$mysql_user
MYSQL_PASSWORD=$mysql_password
MYSQL_DATABASE=$mysql_db

# Sync settings
SYNC_INTERVAL_SECONDS=300
LOG_LEVEL=INFO
EOF

echo "6. Creating database schema..."
mysql -h $mysql_host -P $mysql_port -u $mysql_user -p$mysql_password < mysql_schema.sql

echo "7. Setting up systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Rolling Riches Lead Sync Service
After=network.target mysql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python sync_to_mysql.py --loop --interval 300
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/${SERVICE_NAME}.log
StandardError=append:/var/log/${SERVICE_NAME}.error.log

[Install]
WantedBy=multi-user.target
EOF

echo "8. Setting permissions..."
chown -R $USER:$USER $APP_DIR
chmod 600 $APP_DIR/.env

echo "9. Creating log rotation..."
cat > /etc/logrotate.d/${SERVICE_NAME} << EOF
/var/log/${SERVICE_NAME}.log /var/log/${SERVICE_NAME}.error.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    sharedscripts
    postrotate
        systemctl reload ${SERVICE_NAME} > /dev/null 2>&1 || true
    endscript
}
EOF

echo "10. Starting service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}

echo "11. Setting up monitoring..."
cat > /usr/local/bin/check-leads-sync << 'EOF'
#!/bin/bash
# Check if leads sync is running and alert if not

SERVICE="leads-sync"

if ! systemctl is-active --quiet $SERVICE; then
    echo "Lead sync service is not running!"
    # Add your alert mechanism here (email, SMS, etc.)
    systemctl restart $SERVICE
fi
EOF
chmod +x /usr/local/bin/check-leads-sync

# Add to crontab for monitoring
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/check-leads-sync") | crontab -

echo "==========================================="
echo "Deployment Complete!"
echo "==========================================="
echo ""
echo "Service Status:"
systemctl status ${SERVICE_NAME} --no-pager

echo ""
echo "Useful commands:"
echo "  View logs:        journalctl -u ${SERVICE_NAME} -f"
echo "  Restart service:  systemctl restart ${SERVICE_NAME}"
echo "  Stop service:     systemctl stop ${SERVICE_NAME}"
echo "  Check status:     systemctl status ${SERVICE_NAME}"
echo "  Run manual sync:  cd $APP_DIR && venv/bin/python sync_to_mysql.py --full"
echo ""
echo "The service is now running and will sync leads every 5 minutes."