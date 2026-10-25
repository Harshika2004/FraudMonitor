# System Architecture: Banking Transaction Monitoring & Fraud Risk Analysis

## 1. Architectural Overview

The **Rule-Based Banking Transaction Monitoring and Fraud Risk Analysis System** is structured following modern multi-tier architectural standards:

```mermaid
flowchart TD
    subgraph Presentation_Tier ["Presentation Tier (Frontend)"]
        UI_Dash["Overview Dashboard (HTML5 / Vanilla JS / Chart.js)"]
        UI_Txn["Transactions View (Search / Filter / CSV Import)"]
        UI_Alerts["Alerts Queue & Investigation Dossier"]
        UI_Rules["Rule Configuration Management"]
        UI_Cust["Synthetic Customer & Account Directory"]
    end

    subgraph Application_Tier ["Application Tier (FastAPI Backend)"]
        Router["FastAPI REST Router & Request Validation (Pydantic v2)"]
        Engine["Deterministic Fraud Detection Engine"]
        
        subgraph Detection_Rules ["Modular Fraud Rules"]
            R1["Rule A: High-Value Threshold"]
            R2["Rule B: Transaction Velocity"]
            R3["Rule C: Unusual Timing (Off-Hours)"]
            R4["Rule D: Geographic Implausibility (Haversine Speed)"]
            R5["Rule E: Deviant Spending vs Baseline"]
        end

        Scoring["Explainable Risk Scoring & Band Resolution (0-100)"]
        Aggregator["Pandas & SQLAlchemy Analytics Aggregator"]
    end

    subgraph Data_Tier ["Data Tier (Relational Storage)"]
        MySQL[("MySQL Server 8.0 / PyMySQL")]
        Tables["customers | accounts | transactions | fraud_rules | alerts | alert_rule_triggers | investigation_notes | risk_score_configurations"]
    end

    subgraph Analytics_Extension ["Optional Analytics Extension"]
        PowerBI["Power BI Desktop (DirectQuery / Import)"]
    end

    UI_Dash & UI_Txn & UI_Alerts & UI_Rules & UI_Cust -->|REST / JSON| Router
    Router --> Engine
    Engine --> Detection_Rules
    Detection_Rules --> Scoring
    Router --> Aggregator
    Engine & Aggregator & Router -->|SQLAlchemy ORM Connection Pool| MySQL
    MySQL --- Tables
    MySQL -.->|ODBC / MySQL Connector| PowerBI
```

---

## 2. Component Breakdown

### 2.1 Presentation Tier (Frontend)
- **Zero-Build Stack**: Native HTML5, CSS3, and Vanilla JavaScript (ES6+). No complex node tooling (npm, webpack, Vite) required.
- **Chart.js 4.4+**: Client-side rendering of dynamic line, bar, doughnut, and pie charts bound directly to live backend REST API responses.
- **Responsive Layout**: Dual-tier sidebar navigation with desktop and laptop optimization.
- **Live State Management**: Single-page application (SPA) patterns for tab navigation, live status updates, modal inspection drawers, and toast alerts.

### 2.2 Application Tier (FastAPI Backend)
- **FastAPI**: High-performance Python 3.13-compatible ASGI web framework.
- **Pydantic V2**: Strict contract enforcement for incoming payload validation and outgoing response serialization.
- **Security & Integrity**:
  - Global CORS middleware restricted to local origins.
  - Parameterized SQLAlchemy queries preventing SQL Injection.
  - Global exception handlers preventing stack trace or credential leaks.

### 2.3 Rule-Based Fraud Detection Engine
- **Deterministic Evaluation**: Replaces non-transparent machine learning models with explainable mathematical and logical rules.
- **Configurable Parameters**: Rules read operational thresholds, time windows, and speed limits directly from the database or configuration file.
- **Auditability**: Every triggered rule generates an audit record in `alert_rule_triggers` detailing exact reasons, parameter thresholds, and contextual calculations.

### 2.4 Data Tier (MySQL Server 8.0)
- Fully normalized schema (3NF) maintaining relational integrity via Foreign Key cascades.
- Indexed timestamps, account identifiers, monetary amounts, and alert statuses for low-latency queries.
- Monetary amounts stored in high-precision `DECIMAL(15, 2)` format.
