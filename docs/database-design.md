# Database Design & Entity Relationship Documentation

## 1. Relational Entity Overview

The system uses a normalized relational schema designed for MySQL 8.0, balancing 3NF normalization with rapid analytical querying.

```mermaid
erDiagram
    CUSTOMERS ||--o{ ACCOUNTS : "owns"
    ACCOUNTS ||--o{ TRANSACTIONS : "processes"
    TRANSACTIONS ||--o| ALERTS : "triggers"
    FRAUD_RULES ||--o{ ALERT_RULE_TRIGGERS : "evaluates"
    ALERTS ||--o{ ALERT_RULE_TRIGGERS : "contains"
    ALERTS ||--o{ INVESTIGATION_NOTES : "logged_under"

    CUSTOMERS {
        int customer_id PK
        string customer_ref UK
        string first_name
        string last_name
        string email
        string phone
        string risk_segment
        string account_status
        datetime created_at
        datetime updated_at
    }

    ACCOUNTS {
        int account_id PK
        string account_number UK
        int customer_id FK
        string account_type
        string currency
        decimal current_balance
        decimal average_monthly_balance
        string status
        datetime created_at
    }

    TRANSACTIONS {
        int transaction_id PK
        string transaction_ref UK
        int account_id FK
        decimal amount
        string currency
        string transaction_type
        string channel
        datetime timestamp
        string location_city
        string location_country
        decimal latitude
        decimal longitude
        string device_id
        string ip_address
        string merchant_name
        string merchant_category
        string status
        boolean is_evaluated
        datetime evaluated_at
        datetime created_at
    }

    FRAUD_RULES {
        int rule_id PK
        string rule_code UK
        string rule_name
        text description
        string rule_type
        json parameters_json
        int risk_points
        boolean is_enabled
        datetime updated_at
    }

    ALERTS {
        int alert_id PK
        string alert_ref UK
        int transaction_id FK, UK
        int risk_score
        string risk_category
        string status
        string resolution_reason
        string assigned_to
        datetime created_at
        datetime updated_at
    }

    ALERT_RULE_TRIGGERS {
        int trigger_id PK
        int alert_id FK
        int rule_id FK
        string rule_code
        string rule_name
        int points_awarded
        text trigger_reason
        json evaluation_context_json
        datetime created_at
    }

    INVESTIGATION_NOTES {
        int note_id PK
        int alert_id FK
        string author
        text note_text
        string action_taken
        datetime created_at
    }

    RISK_SCORE_CONFIGURATIONS {
        int config_id PK
        string category_name UK
        int min_score
        int max_score
        string color_hex
        string description
    }
```

---

## 2. Table Specifications

### 2.1 `customers`
- Stores synthetic personal and contact information.
- Primary Key: `customer_id` (INT AUTO_INCREMENT).
- Unique Key: `customer_ref` (e.g. `CUST-1001`).
- Segments: `STANDARD`, `LOW_RISK`, `HIGH_NET_WORTH`.

### 2.2 `accounts`
- Represents bank depository or credit accounts linked to a customer.
- Foreign Key: `customer_id` referencing `customers.customer_id` with `ON DELETE CASCADE`.
- Numeric Precision: `DECIMAL(15, 2)` for currency safety.

### 2.3 `transactions`
- Core ledger of synthetic financial activity.
- Foreign Key: `account_id` referencing `accounts.account_id` with `ON DELETE CASCADE`.
- Indexing Strategy:
  - Composite Index `(account_id, timestamp)` for rapid velocity and baseline lookups.
  - Index `(is_evaluated)` for filtering pending batches.
  - Index `(timestamp)` for time-series aggregation.

### 2.4 `fraud_rules`
- Stores rules and their dynamic parameters in a structured JSON column (`parameters_json`).
- Prevents hardcoding of rules inside application code.
- Configurable risk points (1 to 100) per rule.

### 2.5 `alerts`
- Generated whenever an evaluated transaction triggers one or more active fraud rules.
- Unique constraint on `transaction_id`: Prevents duplicate alerts for the same transaction evaluation.
- Risk Bands: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Lifecycle Statuses: `OPEN`, `UNDER_INVESTIGATION`, `RESOLVED`.

### 2.6 `alert_rule_triggers`
- Normalizes individual rule evaluations for an alert.
- Avoids storing messy delimited strings inside the `alerts` table.
- Stores `evaluation_context_json` providing full mathematical auditability (e.g. distance in km, implied speed, baseline mean).

### 2.7 `investigation_notes`
- Maintains a strict chronological audit trail of human risk analyst findings, actions taken, and status rationale.
- Foreign Key: `alert_id` referencing `alerts.alert_id`.

### 2.8 `risk_score_configurations`
- Defines continuous risk score thresholds (0-29 Low, 30-59 Medium, 60-79 High, 80-100 Critical) and hex colors.
