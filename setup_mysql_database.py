#!/usr/bin/env python3
"""Set up MySQL database schema for WordPress leads extractor."""

import os
import pymysql
import ssl
from dotenv import load_dotenv

# Load environment
load_dotenv()

def get_db_connection(use_database=False):
    """Get database connection with SSL support for DigitalOcean."""
    config = {
        'host': os.getenv('MYSQL_HOST'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'charset': 'utf8mb4'
    }
    
    if use_database:
        config['database'] = os.getenv('MYSQL_DATABASE')
    
    # Add SSL configuration for DigitalOcean
    if os.getenv('MYSQL_SSL', 'false').lower() == 'true':
        config['ssl'] = {'ssl_disabled': False}
    
    return pymysql.connect(**config)

def create_database():
    """Create the welcomebonushunter database if it doesn't exist."""
    conn = get_db_connection(use_database=False)
    try:
        with conn.cursor() as cursor:
            db_name = os.getenv('MYSQL_DATABASE')
            
            # Check if database exists
            cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
            if cursor.fetchone():
                print(f"Database '{db_name}' already exists")
            else:
                cursor.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"[SUCCESS] Created database '{db_name}'")
            
            conn.commit()
    finally:
        conn.close()

def setup_schema():
    """Set up all tables and procedures."""
    conn = get_db_connection(use_database=True)
    
    try:
        with conn.cursor() as cursor:
            # Main leads table
            print("Creating leads table...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(50),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                signup_date DATE,
                signup_datetime DATETIME,
                
                -- Data quality fields
                email_valid BOOLEAN DEFAULT FALSE,
                email_domain VARCHAR(255),
                phone_valid BOOLEAN DEFAULT FALSE,
                phone_country VARCHAR(2),
                phone_type VARCHAR(20),
                quality_score INT DEFAULT 0,
                
                -- Processing status
                is_processed BOOLEAN DEFAULT FALSE,
                processed_at TIMESTAMP NULL,
                
                -- GHL sync fields
                ghl_synced BOOLEAN DEFAULT FALSE,
                ghl_synced_at TIMESTAMP NULL,
                ghl_contact_id VARCHAR(100),
                ghl_sync_attempts INT DEFAULT 0,
                
                -- Source tracking
                source VARCHAR(100) DEFAULT 'wordpress',
                source_id VARCHAR(100),
                
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                -- Indexes
                INDEX idx_email (email),
                INDEX idx_phone (phone),
                INDEX idx_quality (quality_score),
                INDEX idx_processed (is_processed),
                INDEX idx_signup_date (signup_date),
                INDEX idx_ghl_sync (ghl_synced, ghl_sync_attempts)
            ) ENGINE=InnoDB
            """)
            print("[SUCCESS] Created leads table")
            
            # Sync log table
            print("Creating sync_log table...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sync_type VARCHAR(50) NOT NULL,
                sync_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_completed_at TIMESTAMP NULL,
                
                -- Results
                total_records INT DEFAULT 0,
                new_records INT DEFAULT 0,
                updated_records INT DEFAULT 0,
                failed_records INT DEFAULT 0,
                duplicate_records INT DEFAULT 0,
                
                -- Status
                status ENUM('running', 'completed', 'failed') DEFAULT 'running',
                error_message TEXT,
                
                -- Performance
                duration_seconds INT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                INDEX idx_sync_type (sync_type),
                INDEX idx_status (status),
                INDEX idx_started (sync_started_at)
            ) ENGINE=InnoDB
            """)
            print("[SUCCESS] Created sync_log table")
            
            # GHL sync log table
            print("Creating ghl_sync_log table...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ghl_sync_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lead_id INT NOT NULL,
                email VARCHAR(255) NOT NULL,
                
                -- Request details
                request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                request_body JSON,
                
                -- Response details
                response_status_code INT,
                response_body JSON,
                response_timestamp TIMESTAMP NULL,
                
                -- Processing status
                status ENUM('pending', 'success', 'failed', 'retry') DEFAULT 'pending',
                error_message TEXT,
                retry_count INT DEFAULT 0,
                next_retry_at TIMESTAMP NULL,
                
                -- GHL specific data
                ghl_contact_id VARCHAR(100),
                ghl_location_id VARCHAR(100),
                
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                -- Indexes
                INDEX idx_lead_email (lead_id, email),
                INDEX idx_status (status),
                INDEX idx_retry (status, next_retry_at),
                INDEX idx_request_date (request_timestamp),
                INDEX idx_ghl_contact (ghl_contact_id),
                
                -- Foreign key
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """)
            print("[SUCCESS] Created ghl_sync_log table")
            
            # Email blacklist table
            print("Creating email_blacklist table...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_blacklist (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email_pattern VARCHAR(255) NOT NULL UNIQUE,
                reason VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """)
            
            # Add common blacklist patterns
            blacklist_patterns = [
                ('test@%', 'Test emails'),
                ('%@example.com', 'Example domain'),
                ('%@test.%', 'Test domains')
            ]
            
            for pattern, reason in blacklist_patterns:
                cursor.execute("""
                    INSERT IGNORE INTO email_blacklist (email_pattern, reason)
                    VALUES (%s, %s)
                """, (pattern, reason))
            
            print("[SUCCESS] Created email_blacklist table")
            
            # Create views
            print("Creating views...")
            
            # Lead statistics view
            cursor.execute("""
            CREATE OR REPLACE VIEW lead_statistics AS
            SELECT 
                DATE(signup_date) as signup_day,
                COUNT(*) as total_leads,
                SUM(CASE WHEN email_valid = TRUE THEN 1 ELSE 0 END) as valid_emails,
                SUM(CASE WHEN phone_valid = TRUE THEN 1 ELSE 0 END) as valid_phones,
                AVG(quality_score) as avg_quality_score,
                SUM(CASE WHEN is_processed = TRUE THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN ghl_synced = TRUE THEN 1 ELSE 0 END) as ghl_synced
            FROM leads
            GROUP BY DATE(signup_date)
            ORDER BY signup_day DESC
            """)
            
            # GHL sync status view
            cursor.execute("""
            CREATE OR REPLACE VIEW ghl_sync_status AS
            SELECT 
                DATE(request_timestamp) as sync_date,
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'retry' THEN 1 ELSE 0 END) as pending_retry,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                AVG(CASE WHEN status = 'success' THEN 
                    TIMESTAMPDIFF(SECOND, request_timestamp, response_timestamp) 
                END) as avg_response_time_seconds,
                MAX(retry_count) as max_retries
            FROM ghl_sync_log
            GROUP BY DATE(request_timestamp)
            ORDER BY sync_date DESC
            """)
            
            print("[SUCCESS] Created views")
            
            conn.commit()
            print("\n[SUCCESS] Database schema setup complete!")
            
            # Show table summary
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\nCreated {len(tables)} tables/views:")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                count = cursor.fetchone()[0]
                print(f"  - {table[0]}: {count} records")
                
    finally:
        conn.close()

def test_connection():
    """Test database connection."""
    try:
        conn = get_db_connection(use_database=False)
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            print(f"[SUCCESS] Connected to MySQL {version}")
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MYSQL DATABASE SETUP")
    print("=" * 60)
    
    # Test connection
    print("\nTesting connection...")
    if not test_connection():
        exit(1)
    
    # Create database
    print("\nCreating database...")
    create_database()
    
    # Set up schema
    print("\nSetting up schema...")
    setup_schema()
    
    print("\n" + "=" * 60)
    print("Setup complete! Database is ready for use.")
    print("=" * 60)