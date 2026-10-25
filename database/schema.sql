-- =====================================================================
-- Banking Transaction Monitoring & Fraud Risk Analysis System
-- Database Schema for MySQL 8.0+
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `banking_fraud_monitoring`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `banking_fraud_monitoring`;

-- Drop existing tables in reverse dependency order for clean recreation if needed
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `investigation_notes`;
DROP TABLE IF EXISTS `alert_rule_triggers`;
DROP TABLE IF EXISTS `alerts`;
DROP TABLE IF EXISTS `transactions`;
DROP TABLE IF EXISTS `accounts`;
DROP TABLE IF EXISTS `customers`;
DROP TABLE IF EXISTS `fraud_rules`;
DROP TABLE IF EXISTS `risk_score_configurations`;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Customers Table (Synthetic bank customers)
CREATE TABLE `customers` (
    `customer_id` INT AUTO_INCREMENT PRIMARY KEY,
    `customer_ref` VARCHAR(30) NOT NULL UNIQUE,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(25) NULL,
    `risk_segment` ENUM('LOW_RISK', 'STANDARD', 'HIGH_NET_WORTH') NOT NULL DEFAULT 'STANDARD',
    `account_status` ENUM('ACTIVE', 'SUSPENDED', 'CLOSED') NOT NULL DEFAULT 'ACTIVE',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_customers_status` (`account_status`),
    INDEX `idx_customers_ref` (`customer_ref`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Accounts Table
CREATE TABLE `accounts` (
    `account_id` INT AUTO_INCREMENT PRIMARY KEY,
    `account_number` VARCHAR(34) NOT NULL UNIQUE,
    `customer_id` INT NOT NULL,
    `account_type` ENUM('SAVINGS', 'CHECKING', 'CREDIT', 'BUSINESS') NOT NULL DEFAULT 'CHECKING',
    `currency` VARCHAR(3) NOT NULL DEFAULT 'USD',
    `current_balance` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    `average_monthly_balance` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    `status` ENUM('ACTIVE', 'DORMANT', 'FROZEN', 'CLOSED') NOT NULL DEFAULT 'ACTIVE',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_accounts_customer` FOREIGN KEY (`customer_id`) 
        REFERENCES `customers` (`customer_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_accounts_customer_id` (`customer_id`),
    INDEX `idx_accounts_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Transactions Table
CREATE TABLE `transactions` (
    `transaction_id` INT AUTO_INCREMENT PRIMARY KEY,
    `transaction_ref` VARCHAR(50) NOT NULL UNIQUE,
    `account_id` INT NOT NULL,
    `amount` DECIMAL(15, 2) NOT NULL,
    `currency` VARCHAR(3) NOT NULL DEFAULT 'USD',
    `transaction_type` ENUM('TRANSFER', 'DEPOSIT', 'WITHDRAWAL', 'CARD_PAYMENT', 'ONLINE_PURCHASE') NOT NULL,
    `channel` ENUM('ATM', 'BRANCH', 'ONLINE', 'MOBILE_APP', 'POS') NOT NULL DEFAULT 'ONLINE',
    `timestamp` DATETIME NOT NULL,
    `location_city` VARCHAR(60) NOT NULL,
    `location_country` VARCHAR(60) NOT NULL DEFAULT 'USA',
    `latitude` DECIMAL(10, 6) NULL,
    `longitude` DECIMAL(10, 6) NULL,
    `device_id` VARCHAR(100) NULL,
    `ip_address` VARCHAR(45) NULL,
    `merchant_name` VARCHAR(100) NULL,
    `merchant_category` VARCHAR(50) NULL,
    `status` ENUM('COMPLETED', 'PENDING', 'REVERSED', 'FAILED') NOT NULL DEFAULT 'COMPLETED',
    `is_evaluated` BOOLEAN NOT NULL DEFAULT FALSE,
    `evaluated_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_transactions_account` FOREIGN KEY (`account_id`) 
        REFERENCES `accounts` (`account_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_transactions_account_timestamp` (`account_id`, `timestamp`),
    INDEX `idx_transactions_evaluated` (`is_evaluated`),
    INDEX `idx_transactions_timestamp` (`timestamp`),
    INDEX `idx_transactions_amount` (`amount`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Fraud Rules Configuration Table
CREATE TABLE `fraud_rules` (
    `rule_id` INT AUTO_INCREMENT PRIMARY KEY,
    `rule_code` VARCHAR(50) NOT NULL UNIQUE,
    `rule_name` VARCHAR(100) NOT NULL,
    `description` TEXT NOT NULL,
    `rule_type` ENUM('THRESHOLD', 'FREQUENCY', 'TEMPORAL', 'GEOGRAPHIC', 'STATISTICAL') NOT NULL,
    `parameters_json` JSON NOT NULL,
    `risk_points` INT NOT NULL,
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_rules_code` (`rule_code`),
    INDEX `idx_rules_enabled` (`is_enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Risk Score Configurations (Band Definitions)
CREATE TABLE `risk_score_configurations` (
    `config_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_name` ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL UNIQUE,
    `min_score` INT NOT NULL,
    `max_score` INT NOT NULL,
    `color_hex` VARCHAR(10) NOT NULL,
    `description` VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Alerts Table
CREATE TABLE `alerts` (
    `alert_id` INT AUTO_INCREMENT PRIMARY KEY,
    `alert_ref` VARCHAR(50) NOT NULL UNIQUE,
    `transaction_id` INT NOT NULL UNIQUE,
    `risk_score` INT NOT NULL,
    `risk_category` ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL,
    `status` ENUM('OPEN', 'UNDER_INVESTIGATION', 'RESOLVED') NOT NULL DEFAULT 'OPEN',
    `resolution_reason` ENUM('FALSE_POSITIVE', 'CONFIRMED_SUSPICIOUS', 'CUSTOMER_VERIFIED', 'ESCALATED') NULL,
    `assigned_to` VARCHAR(60) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_alerts_transaction` FOREIGN KEY (`transaction_id`) 
        REFERENCES `transactions` (`transaction_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_alerts_status` (`status`),
    INDEX `idx_alerts_category` (`risk_category`),
    INDEX `idx_alerts_score` (`risk_score`),
    INDEX `idx_alerts_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Alert Rule Triggers (Detail / Audit Table for explainable risk indicators)
CREATE TABLE `alert_rule_triggers` (
    `trigger_id` INT AUTO_INCREMENT PRIMARY KEY,
    `alert_id` INT NOT NULL,
    `rule_id` INT NOT NULL,
    `rule_code` VARCHAR(50) NOT NULL,
    `rule_name` VARCHAR(100) NOT NULL,
    `points_awarded` INT NOT NULL,
    `trigger_reason` TEXT NOT NULL,
    `evaluation_context_json` JSON NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_triggers_alert` FOREIGN KEY (`alert_id`) 
        REFERENCES `alerts` (`alert_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_triggers_rule` FOREIGN KEY (`rule_id`) 
        REFERENCES `fraud_rules` (`rule_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX `idx_triggers_alert_id` (`alert_id`),
    INDEX `idx_triggers_rule_id` (`rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Investigation Notes Table
CREATE TABLE `investigation_notes` (
    `note_id` INT AUTO_INCREMENT PRIMARY KEY,
    `alert_id` INT NOT NULL,
    `author` VARCHAR(60) NOT NULL DEFAULT 'Risk Analyst',
    `note_text` TEXT NOT NULL,
    `action_taken` VARCHAR(60) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notes_alert` FOREIGN KEY (`alert_id`) 
        REFERENCES `alerts` (`alert_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_notes_alert_id` (`alert_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- Seed Default Configurable Fraud Rules
-- =====================================================================
INSERT INTO `fraud_rules` (`rule_code`, `rule_name`, `description`, `rule_type`, `parameters_json`, `risk_points`, `is_enabled`)
VALUES
(
    'RULE_HIGH_VALUE',
    'High-Value Transaction Threshold',
    'Flags single transactions exceeding a configured monetary threshold.',
    'THRESHOLD',
    '{"threshold": 10000.00, "currency": "USD"}',
    35,
    TRUE
),
(
    'RULE_VELOCITY',
    'High Transaction Velocity',
    'Detects rapid repeated transactions on the same account within a configured time window.',
    'FREQUENCY',
    '{"time_window_minutes": 60, "transaction_count_threshold": 3}',
    30,
    TRUE
),
(
    'RULE_UNUSUAL_TIMING',
    'Unusual Transaction Timing',
    'Identifies transactions processed during atypical off-hours (default: 01:00 to 05:00 AM local time).',
    'TEMPORAL',
    '{"start_hour": 1, "end_hour": 5}',
    20,
    TRUE
),
(
    'RULE_GEO_ANOMALY',
    'Geographic Implausibility (Impossible Speed)',
    'Detects consecutive transactions across distant locations at physically implausible travel speeds (> 800 km/h).',
    'GEOGRAPHIC',
    '{"speed_threshold_kmh": 800.0, "time_window_hours": 12}',
    40,
    TRUE
),
(
    'RULE_UNUSUAL_SPENDING',
    'Deviant Spending vs Historical Baseline',
    'Compares transaction amount against the customer 30-day historical mean; flags amounts exceeding multiplier * mean (requires minimum 5 historical transactions).',
    'STATISTICAL',
    '{"baseline_multiplier": 3.0, "min_historical_txns": 5, "lookback_days": 30}',
    25,
    TRUE
);

-- =====================================================================
-- Seed Risk Score Band Configurations
-- Low: 0-29, Medium: 30-59, High: 60-79, Critical: 80-100
-- =====================================================================
INSERT INTO `risk_score_configurations` (`category_name`, `min_score`, `max_score`, `color_hex`, `description`)
VALUES
('LOW', 0, 29, '#10b981', 'Low risk indicator - routine activity with minor anomalies'),
('MEDIUM', 30, 59, '#f59e0b', 'Medium risk indicator - requires review if repeated'),
('HIGH', 60, 79, '#f97316', 'High risk indicator - priority investigation required'),
('CRITICAL', 80, 100, '#ef4444', 'Critical risk indicator - immediate operational hold recommended');
