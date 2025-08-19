-- Go High Level Integration Schema Updates
-- Adds response logging and sync tracking for GHL API

USE rolling_riches_leads;

-- Table to log all GHL API responses
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
    ghl_contact_id VARCHAR(100),  -- ID returned by GHL when contact is created
    ghl_location_id VARCHAR(100),  -- Sub-account ID used
    
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
) ENGINE=InnoDB;

-- Add GHL sync status to leads table
ALTER TABLE leads 
ADD COLUMN IF NOT EXISTS ghl_synced BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS ghl_synced_at TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS ghl_contact_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS ghl_sync_attempts INT DEFAULT 0,
ADD INDEX idx_ghl_sync (ghl_synced, ghl_sync_attempts);

-- Table for daily retry summary
CREATE TABLE IF NOT EXISTS ghl_retry_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_attempts INT DEFAULT 0,
    successful_retries INT DEFAULT 0,
    failed_retries INT DEFAULT 0,
    pending_retries INT DEFAULT 0,
    
    -- Timing
    retry_started_at TIMESTAMP NULL,
    retry_completed_at TIMESTAMP NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_date (date)
) ENGINE=InnoDB;

-- View for monitoring GHL sync status
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
ORDER BY sync_date DESC;

-- View for failed leads that need attention
CREATE OR REPLACE VIEW ghl_failed_leads AS
SELECT 
    l.id as lead_id,
    l.email,
    l.phone,
    l.signup_date,
    g.status,
    g.retry_count,
    g.error_message,
    g.request_timestamp as last_attempt,
    g.next_retry_at
FROM leads l
INNER JOIN (
    SELECT lead_id, MAX(id) as latest_id
    FROM ghl_sync_log
    GROUP BY lead_id
) latest ON l.id = latest.lead_id
INNER JOIN ghl_sync_log g ON g.id = latest.latest_id
WHERE g.status IN ('failed', 'retry')
ORDER BY g.request_timestamp DESC;

-- Stored procedure to mark leads for retry
DELIMITER $$

CREATE PROCEDURE mark_for_ghl_retry(
    IN p_max_retries INT,
    IN p_retry_delay_minutes INT
)
BEGIN
    -- Mark failed leads for retry (up to max_retries attempts)
    UPDATE ghl_sync_log
    SET 
        status = 'retry',
        next_retry_at = DATE_ADD(NOW(), INTERVAL p_retry_delay_minutes MINUTE)
    WHERE 
        status = 'failed'
        AND retry_count < p_max_retries
        AND (next_retry_at IS NULL OR next_retry_at < NOW());
        
    -- Return count of marked leads
    SELECT ROW_COUNT() as marked_for_retry;
END$$

DELIMITER ;

-- Stored procedure for end-of-day retry
DELIMITER $$

CREATE PROCEDURE retry_all_failed_ghl_leads()
BEGIN
    DECLARE retry_date DATE;
    SET retry_date = CURDATE();
    
    -- Create retry summary entry
    INSERT INTO ghl_retry_summary (date, retry_started_at, total_attempts)
    VALUES (retry_date, NOW(), 0)
    ON DUPLICATE KEY UPDATE 
        retry_started_at = NOW(),
        total_attempts = 0;
    
    -- Mark all failed leads from today for retry
    UPDATE ghl_sync_log
    SET 
        status = 'retry',
        next_retry_at = NOW(),
        retry_count = retry_count + 1
    WHERE 
        DATE(request_timestamp) = retry_date
        AND status = 'failed';
    
    -- Update summary with attempt count
    UPDATE ghl_retry_summary
    SET total_attempts = (
        SELECT COUNT(*) 
        FROM ghl_sync_log 
        WHERE DATE(request_timestamp) = retry_date 
        AND status = 'retry'
    )
    WHERE date = retry_date;
    
    SELECT 
        COUNT(*) as leads_marked_for_retry,
        retry_date as retry_date
    FROM ghl_sync_log
    WHERE 
        DATE(request_timestamp) = retry_date
        AND status = 'retry';
END$$

DELIMITER ;

-- Function to get next lead to sync
DELIMITER $$

CREATE FUNCTION get_next_ghl_sync_lead() 
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE next_lead_id INT;
    
    -- Get next unsynced lead or retry
    SELECT l.id INTO next_lead_id
    FROM leads l
    LEFT JOIN ghl_sync_log g ON l.id = g.lead_id
    WHERE 
        (l.ghl_synced = FALSE AND g.id IS NULL)  -- Never attempted
        OR (g.status = 'retry' AND (g.next_retry_at IS NULL OR g.next_retry_at <= NOW()))  -- Ready for retry
    ORDER BY 
        CASE WHEN g.status = 'retry' THEN 0 ELSE 1 END,  -- Prioritize retries
        l.quality_score DESC,  -- Then by quality
        l.signup_date ASC  -- Then by oldest first
    LIMIT 1;
    
    RETURN next_lead_id;
END$$

DELIMITER ;