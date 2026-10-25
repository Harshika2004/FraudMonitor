# Viva Voce Preparation Guide

## Final Year Project Viva Preparation

This document prepares you to explain, defend, and demonstrate your **Rule-Based Banking Transaction Monitoring and Fraud Risk Analysis System** during an academic project viva or interview.

---

### Q1: Why did you choose a rule-based system instead of Machine Learning or Deep Learning?

**Answer:**
1. **Explainability and Regulatory Compliance**: Under banking regulations (such as GDPR Article 22, US Fair Credit Reporting Act, and Basel Committee guidelines), financial institutions are legally mandated to explain *why* a customer's transaction or account was blocked or flagged. Black-box ML models (e.g. neural networks, XGBoost) provide probability scores without unambiguous legal explainability.
2. **Determinism and Consistency**: In banking, identical financial facts must always produce the identical legal and risk outcome. Deterministic rules ensure that if a rule is triggered, the system can cite the exact parameter (e.g. *"Transaction amount \$15,000 exceeds \$10,000 threshold"*).
3. **Cold Start & Zero-History Safety**: ML models hallucinate or fail when there is little or no prior customer history. In our rule engine, if a customer has fewer than 5 transactions, the system explicitly returns `insufficient_data=True` instead of fabricating a statistical baseline.
4. **Agility**: A risk officer can update an off-hours window or velocity threshold in 5 seconds via the UI without retraining, revalidating, or deploying heavy ML model pipelines.

---

### Q2: What is the difference between "Confirmed Fraud" and a "Risk Indicator"?

**Answer:**
A transaction monitoring system is a **first-line detection filter**, not a court of law. Flagged transactions are **"potentially suspicious risk indicators"**, indicating that the activity deviated from expected norms or exceeded a risk threshold. Only human risk analysts, compliance officers, and law enforcement can confirm actual fraudulent intent following an investigation. Claiming an automated system has confirmed fraud would create severe legal liability and false-positive harassment of customers.

---

### Q3: How is the Risk Score calculated? Is it a probability?

**Answer:**
No, the Risk Score is **not a probability percentage**. It is an **explainable prioritization metric** ranging from 0 to 100:
1. Each active rule is awarded a configured number of risk points when its condition is met (e.g. High Value = 35 pts, Velocity = 30 pts, Off-Hours = 20 pts, Geo Implausibility = 40 pts, Spending Baseline = 25 pts).
2. The engine sums the points from all triggered rules for that transaction.
3. The sum is capped at 100:
   \[
   \text{Score} = \min\left(\sum \text{points}, 100\right)
   \]
4. The numerical score is mapped to calibrated, continuous bands:
   - **0 – 29**: LOW risk indicator (routine)
   - **30 – 59**: MEDIUM risk indicator (standard review)
   - **60 – 79**: HIGH risk indicator (priority investigation)
   - **80 – 100**: CRITICAL risk indicator (immediate operational hold)

---

### Q4: How does the Geographic Anomaly Rule prevent false positives?

**Answer:**
Many naive systems flag an alert whenever a transaction occurs in a city different from the previous transaction. That causes terrible false positives for travelers or online shoppers.
Our system implements the **Haversine Great-Circle Distance Formula**:
\[
a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)
\]
\[
d = 2 R \cdot \arctan2(\sqrt{a}, \sqrt{1-a})
\]
It calculates the time difference \(\Delta t\) in hours between the consecutive transactions. The implied physical velocity is:
\[
v = \frac{d}{\Delta t}
\]
The rule **only flags** if:
1. The distance \(d > 25\text{ km}\), AND
2. The implied speed \(v > 800\text{ km/h}\) (which is physically impossible even on commercial airliners once ground transport and boarding times are factored in).
If someone transacts in New York at 10:00 AM and in Philadelphia (150 km) at 1:00 PM, the speed is 50 km/h, which is completely plausible, so the rule does **not** trigger.

---

### Q5: How is data integrity and relational structure designed in MySQL?

**Answer:**
1. **Third Normal Form (3NF)**:
   - Customers have independent profile records.
   - Accounts belong to a customer via Foreign Key `customer_id` with `ON DELETE CASCADE`.
   - Transactions belong to an account via Foreign Key `account_id` with `ON DELETE CASCADE`.
   - Alerts maintain a `UNIQUE` foreign key constraint on `transaction_id` to guarantee that one transaction cannot have duplicate alerts created by repeated evaluation runs (Idempotency).
   - Individual triggered rules are stored in a dedicated detail table `alert_rule_triggers` (1-to-many relationship with alerts).
   - Investigation notes are recorded in `investigation_notes` with author and timestamp.
2. **Monetary Precision**: We explicitly use `DECIMAL(15, 2)` instead of `FLOAT` or `DOUBLE` to avoid floating-point rounding errors in financial transactions.
3. **Database Indexing**:
   - Composite index on `(account_id, timestamp)` allows the velocity rule to check recent transactions in sub-millisecond execution time.
   - Indexes on `(is_evaluated)` and `(risk_category)` optimize queue filtering.

---

### Q6: How did you implement security and credential protection?

**Answer:**
1. **Zero Hardcoded Secrets**: All database host, port, username, and password credentials are loaded from an isolated `.env` file via `pydantic-settings` and `python-dotenv`.
2. **Git Safeguards**: `.env`, virtual environments, and temporary log files are strictly excluded via `.gitignore`. A `.env.example` file is provided as a documentation template.
3. **Query Parameterization**: Every database query is executed through SQLAlchemy's parameterized query builder, eliminating SQL Injection vulnerabilities.
4. **Exception Masking**: A global FastAPI exception handler intercepts unhandled server errors and logs the traceback internally, returning a sanitized HTTP 500 JSON response so internal database passwords or stack traces are never leaked to the client browser.
5. **CORS Hardening**: CORS middleware is strictly scoped to local development origins (`http://localhost:8000`, `http://127.0.0.1:8000`).

---

### Q7: What are the current limitations of this system and how can it be enhanced in the future?

**Answer:**
- **Current Limitations**:
  1. The system relies on synthetic data rather than real live banking core switches (e.g. ISO 8583 / ISO 20022 message streams).
  2. Geographic speed assumes straight great-circle paths, which does not account for specific airline flight schedules.
  3. Batch evaluations currently run synchronously via API requests rather than an enterprise distributed event bus (like Apache Kafka).
- **Future Enhancements**:
  1. Integrating streaming ingestion via Apache Kafka or RabbitMQ for sub-second real-time transaction processing.
  2. Adding IP Geolocation database lookups (e.g. MaxMind GeoIP2) and device fingerprint risk hashing.
  3. Implementing role-based access control (RBAC) with JWT tokens and OAuth2 for Multi-Analyst compliance teams.
