#!/bin/bash

# WordPress Leads Sync - Ubuntu Deployment Script
# This script sets up the complete sync system on Ubuntu server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="wordpress-leads-sync"
PROJECT_DIR="/opt/${PROJECT_NAME}"
SERVICE_USER="www-data"
GITHUB_REPO="https://github.com/danielsouza-lab/welcomebonushunter.com-leads-extractor.git"
PYTHON_VERSION="3.8"

# Functions
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

print_status "Starting deployment of WordPress Leads Sync..."

# Step 1: Update system
print_status "Updating system packages..."
apt-get update
apt-get upgrade -y

# Step 2: Install dependencies
print_status "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    mysql-client \
    supervisor \
    nginx \
    certbot \
    python3-certbot-nginx

# Step 3: Create project directory
print_status "Setting up project directory..."
if [ -d "$PROJECT_DIR" ]; then
    print_warning "Project directory exists. Backing up..."
    mv "$PROJECT_DIR" "${PROJECT_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Step 4: Clone repository
print_status "Cloning repository from GitHub..."
git clone "$GITHUB_REPO" .

# Step 5: Set up Python virtual environment
print_status "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Step 6: Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 7: Create .env file
print_status "Creating environment configuration..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# WordPress Configuration
WORDPRESS_URL=
WORDPRESS_USERNAME=
WORDPRESS_PASSWORD=

# MySQL Database Configuration
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
MYSQL_SSL=true

# Go High Level Configuration
GHL_ACCESS_TOKEN=
GHL_LOCATION_ID=
GHL_API_VERSION=2021-07-28
GHL_BATCH_SIZE=10
GHL_MAX_RETRIES=3
GHL_RETRY_DELAY_MINUTES=30

# Sync Configuration
SYNC_INTERVAL_MINUTES=10
EOF
    
    print_warning "Please edit ${PROJECT_DIR}/.env with your credentials"
else
    print_status ".env file already exists, skipping..."
fi

# Step 8: Set up log directory
print_status "Setting up logging..."
mkdir -p /var/log/${PROJECT_NAME}
chown ${SERVICE_USER}:${SERVICE_USER} /var/log/${PROJECT_NAME}

# Step 9: Create systemd service
print_status "Creating systemd service..."
cat > /etc/systemd/system/${PROJECT_NAME}.service << EOF
[Unit]
Description=WordPress Leads Sync Service
After=network.target mysql.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/unified_sync.py --continuous
Restart=always
RestartSec=60
StandardOutput=append:/var/log/${PROJECT_NAME}/service.log
StandardError=append:/var/log/${PROJECT_NAME}/error.log

# Security
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/${PROJECT_NAME}

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Create monitoring script
print_status "Creating monitoring script..."
cat > ${PROJECT_DIR}/monitor.sh << 'EOF'
#!/bin/bash

# Check service status
SERVICE_NAME="wordpress-leads-sync"
LOG_DIR="/var/log/${SERVICE_NAME}"

echo "=== WordPress Leads Sync Monitor ==="
echo "Time: $(date)"
echo

# Check service status
echo "Service Status:"
systemctl status ${SERVICE_NAME} --no-pager | head -n 10

echo
echo "Recent Logs (last 20 lines):"
tail -n 20 ${LOG_DIR}/service.log 2>/dev/null || echo "No logs found"

echo
echo "Recent Errors (last 10 lines):"
tail -n 10 ${LOG_DIR}/error.log 2>/dev/null || echo "No errors found"

echo
echo "Database Stats:"
python3 ${PROJECT_DIR}/unified_sync.py --test 2>/dev/null | grep -E "\[OK\]|\[FAIL\]"
EOF

chmod +x ${PROJECT_DIR}/monitor.sh

# Step 11: Create update script
print_status "Creating update script..."
cat > ${PROJECT_DIR}/update.sh << 'EOF'
#!/bin/bash

set -e

echo "Updating WordPress Leads Sync..."

# Stop service
systemctl stop wordpress-leads-sync

# Pull latest changes
cd /opt/wordpress-leads-sync
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
systemctl start wordpress-leads-sync

echo "Update complete!"
systemctl status wordpress-leads-sync --no-pager | head -n 5
EOF

chmod +x ${PROJECT_DIR}/update.sh

# Step 12: Set permissions
print_status "Setting permissions..."
chown -R ${SERVICE_USER}:${SERVICE_USER} ${PROJECT_DIR}
chmod 600 ${PROJECT_DIR}/.env

# Step 13: Create cron job for log rotation
print_status "Setting up log rotation..."
cat > /etc/logrotate.d/${PROJECT_NAME} << EOF
/var/log/${PROJECT_NAME}/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 640 ${SERVICE_USER} ${SERVICE_USER}
    sharedscripts
    postrotate
        systemctl reload ${PROJECT_NAME} > /dev/null 2>&1 || true
    endscript
}
EOF

# Step 14: Enable and start service
print_status "Enabling service..."
systemctl daemon-reload
systemctl enable ${PROJECT_NAME}

# Step 15: Create management commands
print_status "Creating management commands..."
cat > /usr/local/bin/wp-sync << EOF
#!/bin/bash

case "\$1" in
    start)
        systemctl start ${PROJECT_NAME}
        ;;
    stop)
        systemctl stop ${PROJECT_NAME}
        ;;
    restart)
        systemctl restart ${PROJECT_NAME}
        ;;
    status)
        systemctl status ${PROJECT_NAME}
        ;;
    logs)
        tail -f /var/log/${PROJECT_NAME}/service.log
        ;;
    errors)
        tail -f /var/log/${PROJECT_NAME}/error.log
        ;;
    monitor)
        ${PROJECT_DIR}/monitor.sh
        ;;
    update)
        ${PROJECT_DIR}/update.sh
        ;;
    test)
        cd ${PROJECT_DIR} && source venv/bin/activate && python unified_sync.py --test
        ;;
    *)
        echo "Usage: wp-sync {start|stop|restart|status|logs|errors|monitor|update|test}"
        exit 1
        ;;
esac
EOF

chmod +x /usr/local/bin/wp-sync

# Final message
echo
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo
echo "Next steps:"
echo "1. Edit the configuration file:"
echo "   nano ${PROJECT_DIR}/.env"
echo
echo "2. Test the connection:"
echo "   wp-sync test"
echo
echo "3. Start the service:"
echo "   wp-sync start"
echo
echo "4. Monitor the service:"
echo "   wp-sync monitor"
echo "   wp-sync logs"
echo
echo "Available commands:"
echo "  wp-sync start    - Start the sync service"
echo "  wp-sync stop     - Stop the sync service"
echo "  wp-sync restart  - Restart the sync service"
echo "  wp-sync status   - Check service status"
echo "  wp-sync logs     - View live logs"
echo "  wp-sync errors   - View error logs"
echo "  wp-sync monitor  - Show monitoring dashboard"
echo "  wp-sync update   - Update from GitHub"
echo "  wp-sync test     - Test all connections"
echo
echo "The service will automatically sync every 10 minutes once started."
echo