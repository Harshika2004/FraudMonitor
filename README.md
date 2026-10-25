# Rule-Based Banking Transaction Monitoring and Fraud Risk Analysis System

> **Final-Year Computer Science Engineering Capstone Project**  
> *A deterministic, explainable, and fully functional financial-crime transaction monitoring system built with Python 3.13, FastAPI, SQLAlchemy, MySQL Server 8, and native web technologies.*

---

## 1. Project Overview & Objectives

In modern regulated banking, anti-money laundering (AML) and counter-terrorist financing (CTF) frameworks require financial institutions to monitor transaction streams continuously.

While black-box machine learning approaches are frequently researched, regulated banking environments legally require **explainable, deterministic, and auditable risk scoring** (e.g. EU GDPR Article 22, US Fair Credit Reporting Act, Basel Committee standards).

This capstone project implements an end-to-end web-based transaction monitoring system that:
1. Ingests and monitors synthetic banking transactions in real-time or batch mode.
2. Applies **5 configurable, deterministic fraud detection rules** (High Value, Velocity, Off-Hours Timing, Geographic Implausibility, and Deviant Spending Baseline).
3. Computes a prioritized, explainable **Risk Score (0–100)** mapped into continuous risk categories (**LOW, MEDIUM, HIGH, CRITICAL**).
4. Generates an auditable investigation dossier for flagged transactions.
5. Provides an interactive web dashboard with **live Chart.js charts**, paginated filtering, CSV transaction batch imports, rule parameter editing, and investigator case notes.

> **Academic Disclaimer**: All customer profiles, account numbers, and transactions utilized in this application are **entirely synthetic**. The system flags **"potentially suspicious risk indicators"**, not confirmed fraud.

---

## 2. Technology Stack & Design Rationale

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6+), Chart.js 4.4 | Clean, zero-build architecture. No complex Node.js/npm tooling required; easy to demonstrate, inspect, and explain during a viva. |
| **Backend API** | Python 3.13, FastAPI, Uvicorn (ASGI) | Asynchronous, high-performance REST APIs with automatic OpenAPI (Swagger) documentation and high maintainability. |
| **Data Validation** | Pydantic V2 | Strict data contracts, robust type safety, and automatic validation error reporting. |
| **ORM & Database Access**| SQLAlchemy 2.0+, PyMySQL | Parameterized queries preventing SQL Injection, enterprise connection pooling, and seamless portability. |
| **Relational Database** | MySQL Server 8.0, MySQL Workbench | Normalized schema (3NF) with Foreign Key cascades, indexes, and precision financial arithmetic via `DECIMAL(15, 2)`. |
| **Data Analytics** | Pandas | Efficient time-series and multi-dimensional grouping for dashboard aggregations. |
| **Automated Testing** | pytest, FastAPI TestClient (`httpx`) | 20 comprehensive automated unit, boundary, idempotency, and API integration tests. |
| **BI Extension** | Power BI Desktop | Supported relational database connection for executive business intelligence reporting. |

---

## 3. Project Directory Structure

```
Banking-Fraud-Monitoring/
│
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint & static mounting
│   │   ├── core/
│   │   │   └── config.py               # Pydantic BaseSettings environment loader
│   │   ├── database/
│   │   │   ├── base.py                 # SQLAlchemy declarative base
│   │   │   └── connection.py           # Engine & connection pool configuration
│   │   ├── models/                     # SQLAlchemy relational database entities
│   │   │   ├── customer.py             # Customers table
│   │   │   ├── account.py              # Accounts table
│   │   │   ├── transaction.py          # Transactions table
│   │   │   ├── rule.py                 # Fraud detection rules table
│   │   │   ├── alert.py                # Alerts & AlertRuleTriggers tables
│   │   │   ├── investigation_note.py   # Analyst investigation notes table
│   │   │   └── risk_config.py          # Risk score band definitions table
│   │   ├── schemas/                    # Pydantic request/response schemas
│   │   │   ├── customer.py
│   │   │   ├── account.py
│   │   │   ├── transaction.py
│   │   │   ├── rule.py
│   │   │   ├── alert.py
│   │   │   └── analytics.py
│   │   ├── api/                        # REST API endpoint route handlers
│   │   │   ├── routes_health.py        # Health check & DB ping
│   │   │   ├── routes_transactions.py  # Transaction listing, CSV import, evaluation
│   │   │   ├── routes_alerts.py        # Alerts queue, status update, case notes
│   │   │   ├── routes_rules.py         # Configurable rules management
│   │   │   ├── routes_analytics.py     # Dashboard KPI & chart aggregations
│   │   │   └── routes_customers.py     # Synthetic customer directory
│   │   ├── services/                   # Business logic service layer
│   │   │   ├── transaction_service.py
│   │   │   ├── alert_service.py
│   │   │   └── rule_service.py
│   │   ├── rules/                      # Deterministic Fraud Detection Engine
│   │   │   ├── base.py                 # Abstract base rule class & evaluation result
│   │   │   ├── high_value.py           # Rule A: High monetary threshold
│   │   │   ├── velocity.py             # Rule B: High transaction frequency in window
│   │   │   ├── unusual_timing.py       # Rule C: Off-hours transaction execution
│   │   │   ├── geographic_anomaly.py   # Rule D: Impossible travel speed (Haversine)
│   │   │   ├── unusual_spending.py     # Rule E: Deviant spending vs 30-day baseline
│   │   │   └── engine.py               # Orchestrator & explainable risk scoring
│   │   └── analytics/
│   │       └── aggregator.py           # Pandas time-series & KPI calculator
│   ├── tests/                          # Automated Pytest Suite (20 tests)
│   │   ├── conftest.py                 # In-memory test fixtures (StaticPool)
│   │   ├── test_rules.py               # Unit tests for all 5 rules & edge cases
│   │   ├── test_scoring.py             # Scoring bounds, idempotency, disabled rules
│   │   ├── test_api.py                 # REST API endpoints & error cases
│   │   └── test_frontend_routes.py     # Static route verification
│   ├── requirements.txt                # Python dependencies
│   ├── .env.example                    # Environment configuration template
│   └── .env                            # Local configuration (git-ignored)
│
├── frontend/
│   ├── index.html                      # Executive Overview Dashboard with Chart.js
│   ├── transactions.html               # Transaction ledger, filters & CSV importer
│   ├── alerts.html                     # Alert investigation queue & dossier modal
│   ├── rules.html                      # Detection rule parameter configuration
│   ├── customers.html                  # Synthetic customer directory & accounts
│   ├── css/
│   │   └── style.css                   # Responsive, professional banking stylesheet
│   └── js/
│       ├── api.js                      # Centralized API fetch wrapper & formatters
│       ├── dashboard.js                # Chart.js renderers & KPI cards
│       ├── transactions.js             # Table filters, pagination, CSV upload
│       ├── alerts.js                   # Case notes, status updater, investigation
│       ├── rules.js                    # Parameter editing & update confirmation
│       └── customers.js                # Customer profile modal
│
├── database/
│   ├── schema.sql                      # Complete MySQL 8 DDL with constraints & indexes
│   ├── seed_data.py                    # Repeatable synthetic dataset generator
│   ├── init_db.py                      # One-click database initialization runner
│   └── sample_transactions.csv         # Sample CSV for testing file upload in UI
│
├── powerbi/
│   └── README.md                       # Power BI Desktop connection & report guide
│
├── docs/
│   ├── architecture.md                 # Multi-tier system architecture documentation
│   ├── database-design.md              # Relational schema design, ER diagram & 3NF
│   ├── detection-rules.md              # Mathematical detection formulas & scoring matrix
│   ├── testing.md                      # Automated testing methodology & test report
│   ├── viva-preparation.md             # Comprehensive Viva Q&A preparation guide
│   └── Banking_Fraud_Monitoring.postman_collection.json # Importable Postman API collection
│
├── .gitignore                          # Excludes venv, .env, __pycache__, logs
└── README.md                           # Main project documentation
```

---

## 4. Step-by-Step Setup Guide on Windows

### Step 1: Clone or Navigate to the Workspace
Open Windows PowerShell:
```powershell
cd C:\Users\harsh\OneDrive\Desktop\Banking-Fraud-Monitoring
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `backend/.env`:
```powershell
Copy-Item backend\.env.example backend\.env
```

Open `backend\.env` in VS Code or Notepad:
```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD_HERE
DB_NAME=banking_fraud_monitoring
```
*(Enter your MySQL root password. Never commit this file to Git).*

> **Tip for Instant Offline Demo**: If you prefer testing without MySQL Server running, set `DB_URL=sqlite:///./banking_fraud.db` in `backend/.env`.

---

### Step 3: Set Up Python Virtual Environment
The virtual environment is created using Python 3.13:
```powershell
# Create virtual environment inside backend folder
& "C:\Users\harsh\AppData\Local\Programs\Python\Python313\python.exe" -m venv backend\venv

# Install dependencies
& "backend\venv\Scripts\pip.exe" install -r backend\requirements.txt
```

---

### Step 4: Initialize the Database & Generate Synthetic Sample Data
1. Make sure your MySQL service is running:
   ```powershell
   Get-Service -Name MySQL80
   ```
2. Initialize the schema and generate synthetic records:
   ```powershell
   $env:PYTHONPATH="."
   & "backend\venv\Scripts\python.exe" database\init_db.py
   ```
This script automatically:
- Creates all relational tables (`customers`, `accounts`, `transactions`, `fraud_rules`, `alerts`, etc.).
- Seeds 10 synthetic customers with realistic account balances.
- Generates ~400 realistic synthetic transactions across the previous 28 days.
- Injects curated test scenarios (High-value transfers, velocity bursts, off-hours spikes, impossible travel speed, and abnormal baseline spending).
- Evaluates the transaction stream through the Rule Engine to populate initial alerts.

---

### Step 5: Start the FastAPI Backend Server
Run Uvicorn with automatic reload:
```powershell
$env:PYTHONPATH="."
& "backend\venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### Step 6: Access the Application in Your Browser
Open your web browser:
- **Interactive Web Application**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Transactions Stream & CSV Importer**: [http://127.0.0.1:8000/transactions](http://127.0.0.1:8000/transactions)
- **Alerts Investigation Queue**: [http://127.0.0.1:8000/alerts](http://127.0.0.1:8000/alerts)
- **Fraud Rules Configuration**: [http://127.0.0.1:8000/rules](http://127.0.0.1:8000/rules)
- **Synthetic Customer Directory**: [http://127.0.0.1:8000/customers](http://127.0.0.1:8000/customers)
- **Interactive Swagger REST API Docs**: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **ReDoc Technical Specification**: [http://127.0.0.1:8000/api/redoc](http://127.0.0.1:8000/api/redoc)

---

## 5. Running Automated Backend Tests

The project includes 20 automated unit and integration tests covering risk scoring bounds, all 5 detection rules, idempotency, edge cases, and API error scenarios:

```powershell
$env:PYTHONPATH="."
& "backend\venv\Scripts\python.exe" -m pytest backend/tests -v
```

Expected result:
```
backend/tests/test_api.py::test_health_endpoint PASSED
backend/tests/test_api.py::test_create_and_list_transactions PASSED
backend/tests/test_api.py::test_invalid_transaction_amount_rejected PASSED
backend/tests/test_api.py::test_evaluate_single_transaction_api PASSED
backend/tests/test_api.py::test_alert_status_workflow_and_notes PASSED
backend/tests/test_api.py::test_invalid_alert_status_rejected PASSED
backend/tests/test_api.py::test_analytics_dashboard_endpoint PASSED
backend/tests/test_rules.py::test_high_value_rule_triggers_above_threshold PASSED
backend/tests/test_rules.py::test_high_value_rule_does_not_trigger_below_threshold PASSED
backend/tests/test_rules.py::test_velocity_rule_triggers_on_rapid_transactions PASSED
backend/tests/test_rules.py::test_unusual_timing_rule_identifies_off_hours PASSED
backend/tests/test_rules.py::test_geographic_anomaly_detects_impossible_speed PASSED
backend/tests/test_rules.py::test_geographic_anomaly_does_not_flag_plausible_travel PASSED
backend/tests/test_rules.py::test_unusual_spending_insufficient_history PASSED
backend/tests/test_rules.py::test_unusual_spending_triggers_when_exceeding_baseline PASSED
backend/tests/test_scoring.py::test_risk_band_mapping PASSED
backend/tests/test_scoring.py::test_risk_bands_no_gaps_or_overlaps PASSED
backend/tests/test_scoring.py::test_score_capped_at_max PASSED
backend/tests/test_scoring.py::test_duplicate_alert_prevention_idempotency PASSED
backend/tests/test_scoring.py::test_disabled_rule_does_not_fire PASSED
============================== 20 passed in 0.36s ==============================
```

---

## 6. How to Test with Postman

1. Open **Postman Desktop**.
2. Click **Import** in the top-left corner.
3. Select the file:  
   `c:\Users\harsh\OneDrive\Desktop\Banking-Fraud-Monitoring\docs\Banking_Fraud_Monitoring.postman_collection.json`
4. The collection contains pre-configured requests for:
   - System Health Check (`GET /api/health`)
   - Dashboard Analytics (`GET /api/analytics/dashboard`)
   - List Transactions (`GET /api/transactions`)
   - Create Transaction (`POST /api/transactions`)
   - Evaluate Single Transaction (`POST /api/transactions/{id}/evaluate`)
   - Batch Evaluation (`POST /api/transactions/evaluate-batch`)
   - List Alerts Queue (`GET /api/alerts`)
   - Update Alert Status & Resolution (`PATCH /api/alerts/{id}/status`)
   - Add Investigation Note (`POST /api/alerts/{id}/notes`)
   - List & Update Detection Rules (`GET / PUT /api/rules/{id}`)
   - Customer Directory (`GET /api/customers`)

---

## 7. How to Demonstrate in a Viva Voce

Follow this suggested 5-minute live demonstration flow:
1. **Executive Dashboard (`index.html`)**:
   - Point out the KPI summary cards (Total volume, flagged volume, open alerts).
   - Show the dynamic Chart.js time-series chart and explain how flagged alerts correlate with volume.
   - Click **Run Full Evaluation** to demonstrate live backend batch analysis.
2. **Transactions Ledger (`transactions.html`)**:
   - Filter by `Transfer` or `Critical`.
   - Click **View** on a transaction to show the modal with customer, account, and GPS coordinates.
   - Click **Evaluate** on any transaction to demonstrate live, on-demand deterministic rule execution.
   - Show the **Import CSV** feature using `database/sample_transactions.csv`.
3. **Alerts Investigation Queue (`alerts.html`)**:
   - Select a `CRITICAL` or `HIGH` alert and click **Investigate**.
   - Show the **Audit Trail**: explain why the rule was triggered (e.g. *Haversine speed = 7,420 km/h* or *Amount exceeds 3x 30-day baseline*).
   - Transition status from `OPEN` &rarr; `UNDER_INVESTIGATION` &rarr; `RESOLVED`.
   - Add an investigation note with analyst findings.
4. **Detection Rules (`rules.html`)**:
   - Show the 5 configurable rules.
   - Edit the threshold on `High-Value Transaction Threshold` (e.g. from \$10,000 to \$15,000) and save.
   - Explain how parameter changes are persisted in MySQL without code modification.
5. **Customer Directory (`customers.html`)**:
   - Search for a customer and open their profile.
   - Emphasize that risk scores attach to transaction events rather than labeling human beings.

---

## 8. Troubleshooting Common Errors

| Error | Root Cause | Solution |
| :--- | :--- | :--- |
| `ERROR 1045: Access denied for user 'root'@'localhost'` | MySQL password in `.env` is incorrect or missing. | Open `backend/.env` and update `DB_PASSWORD=your_actual_password`. |
| `Can't connect to MySQL server on '127.0.0.1'` | The `MySQL80` Windows service is stopped. | Run `Start-Service -Name MySQL80` in PowerShell as Administrator. |
| `ModuleNotFoundError: No module named 'backend'` | PowerShell did not have project root in `PYTHONPATH`. | Set `$env:PYTHONPATH="."` before running python commands. |
| `ExecutionPolicy SecurityError on profile.ps1` | Windows PowerShell script execution restriction. | The application commands do not require profile scripts; run commands directly or pass `-ExecutionPolicy Bypass`. |

---

## 9. Academic Licensing

Developed as a Final Year Computer Science & Engineering Capstone Project.  
Released under the MIT License for educational and academic demonstration purposes.
