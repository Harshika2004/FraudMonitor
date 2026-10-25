# Deterministic Fraud Detection Rules & Risk Scoring

## 1. Principles of Deterministic Monitoring

Unlike machine learning or AI models, which can be prone to hallucination, black-box unexplainability, and data drift, this system is **100% deterministic, explainable, and audit-compliant**:
- **Same input + unchanged parameters = identical result every single time.**
- **No black-box probability scores**: Flags are classified as "potentially suspicious indicators", never "confirmed fraud".
- **Transparent audit trail**: Every triggered point is backed by an explicit calculation recorded in the database.

---

## 2. Detection Rule Specifications

### Rule A: High-Value Transaction Threshold (`RULE_HIGH_VALUE`)
- **Category**: Threshold / Monetary
- **Default Risk Points**: 35
- **Default Parameters**:
  ```json
  {
    "threshold": 10000.00,
    "currency": "USD"
  }
  ```
- **Detection Logic**:
  Triggers if \(\text{transaction.amount} \ge \text{threshold}\).
- **Limitations**: Legitimate high-net-worth customers or corporate accounts routinely process transactions above \$10,000. It is an indicator of exposure, not guilt.

---

### Rule B: Transaction Velocity (`RULE_VELOCITY`)
- **Category**: Frequency / Temporal
- **Default Risk Points**: 30
- **Default Parameters**:
  ```json
  {
    "time_window_minutes": 60,
    "transaction_count_threshold": 3
  }
  ```
- **Detection Logic**:
  Counts all transactions on the same account within the time interval:
  \[
  t_{\text{current}} - \Delta t \le t_i \le t_{\text{current}}
  \]
  Triggers if \(\text{count} \ge \text{transaction\_count\_threshold}\).
- **Rationale**: Rapid automated card testing, brute force attempts, or compromised card exploitation bursts.

---

### Rule C: Unusual Transaction Timing (`RULE_UNUSUAL_TIMING`)
- **Category**: Temporal / Off-Hours
- **Default Risk Points**: 20
- **Default Parameters**:
  ```json
  {
    "start_hour": 1,
    "end_hour": 5
  }
  ```
- **Detection Logic**:
  Evaluates the hour component of the transaction timestamp (\(H \in [0, 23]\)).
  Triggers if \(1 \le H \le 5\).
- **Rationale**: Early morning off-hours (01:00 AM - 05:00 AM) exhibit lower legitimate consumer volume and higher vulnerability to nocturnal skimming or automated bot scripts.

---

### Rule D: Geographic Implausibility (`RULE_GEO_ANOMALY`)
- **Category**: Geographic / Physical Feasibility
- **Default Risk Points**: 40
- **Default Parameters**:
  ```json
  {
    "speed_threshold_kmh": 800.0,
    "time_window_hours": 12.0
  }
  ```
- **Detection Logic**:
  1. Finds the immediate prior transaction on the same account within 12 hours that has valid coordinates \((lat_1, lon_1)\).
  2. Computes great-circle distance \(d\) using the **Haversine Formula**:
     \[
     a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)
     \]
     \[
     d = 2 R \cdot \arctan2(\sqrt{a}, \sqrt{1-a}) \quad \text{where } R = 6,371 \text{ km}
     \]
  3. Computes time delta \(\Delta t = (t_{\text{curr}} - t_{\text{prev}})\) in hours.
  4. Implied velocity \(v = \frac{d}{\Delta t}\) in km/h.
  5. Triggers **only** if \(d > 25 \text{ km}\) and \(v > 800 \text{ km/h}\).
- **Key Safety Guard**: Does **NOT** flag simply because locations differ! A customer driving from New York to Philadelphia (150 km in 3 hours = 50 km/h) is completely permitted.

---

### Rule E: Deviant Spending vs Baseline (`RULE_UNUSUAL_SPENDING`)
- **Category**: Statistical / Customer Baseline
- **Default Risk Points**: 25
- **Default Parameters**:
  ```json
  {
    "baseline_multiplier": 3.0,
    "min_historical_txns": 5,
    "lookback_days": 30
  }
  ```
- **Detection Logic**:
  1. Gathers prior completed transactions on the same account over the previous 30 days.
  2. **Insufficient History Check**: If prior completed count \(< 5\), returns `insufficient_data=True` and awards **0 points**. The system **never** fabricates a fictitious baseline.
  3. If count \(\ge 5\), computes historical mean:
     \[
     \mu = \frac{1}{N}\sum_{i=1}^N \text{amount}_i
     \]
  4. Triggers if \(\text{amount}_{\text{current}} > \text{multiplier} \cdot \mu\).

---

## 3. Explainable Risk Scoring Matrix

Points from all triggered rules sum up and are capped at 100:
\[
\text{Raw Score} = \sum_{r \in \text{Triggered Rules}} \text{points}_r
\]
\[
\text{Final Risk Score} = \min(\text{Raw Score}, 100)
\]

### Continuous Risk Bands (No Gaps, No Overlaps)
| Risk Band | Score Range | Indicator Interpretation | Recommended Operational Action |
| :--- | :--- | :--- | :--- |
| **LOW** | 0 – 29 | Routine transaction with minor parameter touchpoints | Automated logging; no analyst intervention required |
| **MEDIUM** | 30 – 59 | Moderate anomaly (e.g. single velocity or off-hours flag) | Queued for standard review within 24 hours |
| **HIGH** | 60 – 79 | Compound indicators (e.g. high-value + off-hours) | Priority investigation; cardholder SMS verification |
| **CRITICAL** | 80 – 100 | Severe compound indicators (e.g. impossible speed + high value) | Immediate operational hold / supervisor review |
