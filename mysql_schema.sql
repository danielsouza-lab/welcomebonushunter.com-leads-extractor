-- Rolling Riches Leads Database Schema
-- Clean, optimized structure for lead storage

CREATE DATABASE IF NOT EXISTS rolling_riches_leads
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE rolling_riches_leads;

-- Main leads table with cleaned, validated data
CREATE TABLE IF NOT EXISTS leads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Core fields
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    signup_date DATETIME NOT NULL,
    source VARCHAR(100),
    
    -- Cleaned/standardized fields
    email_domain VARCHAR(255) GENERATED ALWAYS AS (SUBSTRING_INDEX(email, '@', -1)) STORED,
    phone_cleaned VARCHAR(20),  -- Numbers only version
    phone_country_code VARCHAR(10),
    is_mobile BOOLEAN DEFAULT FALSE,
    
    -- Validation flags
    email_valid BOOLEAN DEFAULT TRUE,
    phone_valid BOOLEAN DEFAULT NULL,
    is_duplicate BOOLEAN DEFAULT FALSE,
    
    -- WordPress reference
    wp_id INT,  -- Original ID from WordPress
    wp_source_table VARCHAR(100) DEFAULT 'wp_sweeprewards_signups',
    
    -- Marketing fields
    signup_source VARCHAR(50),  -- hero, footer, popup, etc.
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    referrer_url TEXT,
    landing_page VARCHAR(500),
    
    -- Processing metadata
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at DATETIME,
    
    -- Quality scoring (0-100)
    quality_score INT DEFAULT 50,
    
    -- Notes/flags
    notes TEXT,
    tags JSON,  -- Flexible tagging system
    
    -- Indexes for performance
    INDEX idx_email (email),
    INDEX idx_signup_date (signup_date),
    INDEX idx_processed (processed),
    INDEX idx_source (source, signup_source),
    INDEX idx_quality (quality_score),
    INDEX idx_domain (email_domain),
    INDEX idx_wp_id (wp_id),
    
    -- Ensure no duplicate emails from same source
    UNIQUE KEY unique_email_source (email, wp_id)
) ENGINE=InnoDB;

-- Sync tracking table
CREATE TABLE IF NOT EXISTS sync_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sync_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_completed_at TIMESTAMP NULL,
    last_signup_date_synced DATETIME,
    leads_fetched INT DEFAULT 0,
    leads_inserted INT DEFAULT 0,
    leads_updated INT DEFAULT 0,
    leads_skipped INT DEFAULT 0,
    errors INT DEFAULT 0,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    error_message TEXT,
    
    INDEX idx_status (status),
    INDEX idx_sync_date (sync_started_at)
) ENGINE=InnoDB;

-- Email validation/blacklist table
CREATE TABLE IF NOT EXISTS email_blacklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pattern VARCHAR(255) NOT NULL,
    type ENUM('domain', 'email', 'pattern') DEFAULT 'domain',
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_pattern (pattern)
) ENGINE=InnoDB;

-- Insert common spam/test domains
INSERT IGNORE INTO email_blacklist (pattern, type, reason) VALUES
('test.com', 'domain', 'Test domain'),
('example.com', 'domain', 'Example domain'),
('mailinator.com', 'domain', 'Disposable email'),
('guerrillamail.com', 'domain', 'Disposable email'),
('10minutemail.com', 'domain', 'Disposable email'),
('testing@%', 'pattern', 'Testing emails'),
('test@%', 'pattern', 'Testing emails');

-- Statistics view
CREATE OR REPLACE VIEW lead_statistics AS
SELECT 
    DATE(signup_date) as signup_day,
    COUNT(*) as total_leads,
    COUNT(DISTINCT email) as unique_emails,
    SUM(CASE WHEN email_valid = 1 THEN 1 ELSE 0 END) as valid_emails,
    SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) as with_phone,
    SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) as processed,
    AVG(quality_score) as avg_quality_score,
    GROUP_CONCAT(DISTINCT source) as sources
FROM leads
GROUP BY DATE(signup_date)
ORDER BY signup_day DESC;

-- Daily summary view
CREATE OR REPLACE VIEW daily_summary AS
SELECT 
    CURDATE() as report_date,
    (SELECT COUNT(*) FROM leads WHERE DATE(signup_date) = CURDATE()) as today_leads,
    (SELECT COUNT(*) FROM leads WHERE DATE(signup_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)) as yesterday_leads,
    (SELECT COUNT(*) FROM leads WHERE signup_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as week_leads,
    (SELECT COUNT(*) FROM leads WHERE signup_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as month_leads,
    (SELECT COUNT(*) FROM leads) as total_leads,
    (SELECT COUNT(DISTINCT email) FROM leads) as unique_emails,
    (SELECT AVG(quality_score) FROM leads) as avg_quality;

-- Stored procedure for safe lead insertion with deduplication
DELIMITER $$

CREATE PROCEDURE insert_or_update_lead(
    IN p_email VARCHAR(255),
    IN p_phone VARCHAR(50),
    IN p_signup_date DATETIME,
    IN p_source VARCHAR(100),
    IN p_wp_id INT,
    IN p_signup_source VARCHAR(50)
)
BEGIN
    DECLARE existing_id INT;
    
    -- Check if lead exists
    SELECT id INTO existing_id 
    FROM leads 
    WHERE email = p_email AND wp_id = p_wp_id
    LIMIT 1;
    
    IF existing_id IS NULL THEN
        -- Insert new lead
        INSERT INTO leads (
            email, phone, signup_date, source, wp_id, signup_source,
            phone_cleaned, email_valid
        ) VALUES (
            p_email, 
            p_phone, 
            p_signup_date, 
            p_source, 
            p_wp_id,
            p_signup_source,
            REGEXP_REPLACE(p_phone, '[^0-9]', ''),  -- Clean phone
            p_email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'  -- Validate email
        );
    ELSE
        -- Update existing lead's last sync time
        UPDATE leads 
        SET last_synced_at = CURRENT_TIMESTAMP
        WHERE id = existing_id;
    END IF;
END$$

DELIMITER ;

-- Function to calculate lead quality score
DELIMITER $$

CREATE FUNCTION calculate_quality_score(
    p_email VARCHAR(255),
    p_phone VARCHAR(50),
    p_signup_source VARCHAR(50)
) RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE score INT DEFAULT 50;
    
    -- Valid email format (+20)
    IF p_email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN
        SET score = score + 20;
    END IF;
    
    -- Has phone number (+15)
    IF p_phone IS NOT NULL AND LENGTH(REGEXP_REPLACE(p_phone, '[^0-9]', '')) >= 10 THEN
        SET score = score + 15;
    END IF;
    
    -- Not a free email provider (+10)
    IF p_email NOT LIKE '%gmail.com' 
       AND p_email NOT LIKE '%yahoo.com' 
       AND p_email NOT LIKE '%hotmail.com' THEN
        SET score = score + 10;
    END IF;
    
    -- Good signup source (+5)
    IF p_signup_source NOT IN ('test', 'unknown', '') THEN
        SET score = score + 5;
    END IF;
    
    RETURN LEAST(score, 100);
END$$

DELIMITER ;

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON rolling_riches_leads.* TO 'your_user'@'%';
-- FLUSH PRIVILEGES;