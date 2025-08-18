# WordPress Leads Extractor & MySQL Sync System

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-ready system for extracting leads from WordPress forms and syncing them to a MySQL database with automatic data cleaning, validation, and quality scoring.

## 🌟 Features

- **🔄 Automatic Lead Extraction** - Pulls leads from WordPress via custom REST API
- **🧹 Data Cleaning** - Validates emails, standardizes phone numbers
- **📊 Quality Scoring** - Assigns quality scores (0-100) to each lead
- **🔁 Incremental Sync** - Only processes new leads since last sync
- **🛡️ Duplicate Prevention** - Intelligent deduplication logic
- **📈 Real-time Monitoring** - Track sync status and statistics
- **🚀 Production Ready** - Systemd service, logging, error handling

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [WordPress Plugin](#-wordpress-plugin)
- [Database Schema](#-database-schema)
- [Deployment](#-deployment)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [License](#-license)

## 🏗️ Architecture

```
WordPress Site                    This System                     MySQL Database
┌─────────────┐                ┌──────────────┐               ┌──────────────┐
│   WP Forms  │                │              │               │              │
│      ↓      │                │   Python     │               │   Cleaned    │
│  Custom API │ ──REST API──> │   Extractor  │ ──Insert──>  │    Leads     │
│   Plugin    │                │   & Cleaner  │               │   Database   │
└─────────────┘                └──────────────┘               └──────────────┘
```

## 📦 Prerequisites

- Python 3.8+
- WordPress 5.6+ with admin access
- MySQL 5.7+ or 8.0+
- Linux server for deployment (optional)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/wordpress-leads-extractor.git
cd wordpress-leads-extractor
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install WordPress Plugin

1. Navigate to `wordpress-plugin/rolling-riches-leads-api/`
2. ZIP the folder
3. Upload to WordPress via Plugins → Add New → Upload Plugin
4. Activate the plugin

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required environment variables:
```env
# WordPress
WORDPRESS_URL=https://your-site.com
WORDPRESS_USERNAME=admin_username
WORDPRESS_PASSWORD=application_password

# MySQL
MYSQL_HOST=your-mysql-host.com
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=leads_database
```

### 5. Set Up Database

```bash
# Create database schema
mysql -h your-host -u your-user -p < mysql_schema.sql
```

## 💻 Usage

### Extract Leads Once

```bash
python src/wordpress_leads_extractor/main.py --once
```

### Run Continuous Sync

```bash
python sync_to_mysql.py --loop --interval 300
```

### View Statistics

```bash
python src/wordpress_leads_extractor/main.py --stats
```

### Test Connection

```bash
python test_connection.py
```

### Extract with Filters

```bash
python extract_with_filters.py
```

## 🔌 WordPress Plugin

The custom WordPress plugin (`wordpress-plugin/rolling-riches-leads-api/`) exposes leads via REST API.

### Endpoints

- `GET /wp-json/rolling-riches/v1/leads` - Get leads
- `GET /wp-json/rolling-riches/v1/leads/stats` - Get statistics

### Parameters

- `since` - Get leads after this datetime
- `until` - Get leads before this datetime
- `last_id` - Get leads with ID greater than this
- `limit` - Maximum number of leads to return
- `offset` - Pagination offset

## 🗄️ Database Schema

### Main Tables

#### `leads` Table
- Stores cleaned and validated lead data
- Includes quality scoring
- Tracks processing status

#### `sync_log` Table
- Records sync history
- Tracks success/failure
- Monitors performance

### Views

- `lead_statistics` - Daily lead statistics
- `daily_summary` - Quick dashboard view

## 🚢 Deployment

### Automated Deployment

```bash
# Run deployment script on your server
sudo bash deploy.sh
```

### Manual Deployment

1. Copy files to server
2. Install dependencies
3. Set up systemd service
4. Configure environment
5. Start service

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

### Systemd Service

```bash
# Service management
sudo systemctl start leads-sync
sudo systemctl stop leads-sync
sudo systemctl restart leads-sync
sudo systemctl status leads-sync

# View logs
sudo journalctl -u leads-sync -f
```

## 📚 API Documentation

### WordPress API Client

```python
from src.wordpress_leads_extractor.api.wordpress_client import WordPressClient

client = WordPressClient(
    site_url="https://site.com",
    username="admin",
    password="app_password"
)

# Get all leads
leads = client.get_all_leads()

# Get leads since date
from datetime import datetime, timedelta
since = datetime.now() - timedelta(days=7)
recent_leads = client.get_all_leads(since=since)
```

### Database Operations

```python
from src.wordpress_leads_extractor.database.connection import DatabaseManager, LeadRepository

db = DatabaseManager("mysql://user:pass@host/database")
repo = LeadRepository(db)

# Save lead
lead_id = repo.save_lead(lead_data)

# Get unprocessed leads
unprocessed = repo.get_unprocessed_leads()

# Mark as processed
repo.mark_lead_processed(lead_id)
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_wordpress_client.py
```

## 📊 Monitoring

### Check Sync Status

```sql
-- Recent syncs
SELECT * FROM sync_log 
ORDER BY sync_started_at DESC 
LIMIT 10;

-- Daily statistics
SELECT * FROM lead_statistics 
WHERE signup_day >= DATE_SUB(NOW(), INTERVAL 7 DAY);
```

### Health Checks

```bash
# Check if service is running
systemctl is-active leads-sync

# Check last sync time
mysql -e "SELECT MAX(sync_completed_at) FROM sync_log WHERE status='completed'"
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.