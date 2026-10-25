# Power BI Integration Guide: Banking Fraud Monitoring Extension

This guide provides instructions for connecting **Power BI Desktop** to the MySQL database of the Banking Transaction Monitoring and Fraud Risk Analysis System to build executive reports and business intelligence dashboards.

---

## 1. Prerequisites

1. **Power BI Desktop** installed on your Windows machine.
2. **MySQL Connector / NET** or **MySQL ODBC 8.0 Driver**:
   - Power BI uses the MySQL Connector to connect to MySQL Server 8.0.
   - If not already installed, it can be added via the MySQL Installer for Windows (`C:\Program Files (x86)\MySQL\MySQL Installer for Windows`).
3. Running MySQL Server 8.0 instance with the `banking_fraud_monitoring` database initialized.

---

## 2. Connection Methods: Import vs DirectQuery

| Feature | Import Mode (Recommended) | DirectQuery Mode |
| :--- | :--- | :--- |
| **Performance** | Blazing fast in-memory VertiPaq engine | Query latency dependent on MySQL server speed |
| **Data Freshness** | Refreshed on a scheduled basis or manual click | Real-time queries sent to MySQL on each click |
| **DAX Capabilities** | Full DAX formula support, calculated tables | Limited subset of DAX functions supported |
| **Offline Viewing** | Report can be viewed and interacted with offline | Requires live network connectivity to MySQL |

> **Recommendation**: For academic demonstration, use **Import Mode**. It allows you to save the `.pbix` file with data embedded so you can present your report during a viva even without running MySQL!

---

## 3. Step-by-Step Connection Instructions

1. **Launch Power BI Desktop**.
2. Click **Get Data** &rarr; **More...** &rarr; Select **Database** &rarr; **MySQL database** &rarr; Click **Connect**.
3. In the MySQL database dialog:
   - **Server**: `127.0.0.1:3306` (or `localhost`)
   - **Database**: `banking_fraud_monitoring`
   - **Data Connectivity mode**: Select **Import**.
4. In the Credentials dialog:
   - Select the **Database** tab on the left menu.
   - **User name**: `root`
   - **Password**: Enter your local MySQL password.
   - Click **Connect**.
5. In the **Navigator** window, select the following tables:
   - `customers`
   - `accounts`
   - `transactions`
   - `fraud_rules`
   - `alerts`
   - `alert_rule_triggers`
   - `investigation_notes`
   - `risk_score_configurations`
6. Click **Load** (or **Transform Data** to inspect column data types in Power Query).

---

## 4. Recommended Power BI Report Pages

### Page 1: Executive Risk Dashboard
- **KPI Cards**:
  - Total Monitored Volume (`SUM(transactions[amount])`)
  - Total Alerts (`COUNT(alerts[alert_id])`)
  - Flag Rate Percentage (`[Total Alerts] / [Total Transactions] * 100`)
  - Critical Alerts Count (`CALCULATE(COUNT(alerts[alert_id]), alerts[risk_category] = "CRITICAL")`)
- **Visualizations**:
  - Donut Chart: Alerts by `risk_category` (using calibrated colors: Low=Green, Medium=Amber, High=Orange, Critical=Red).
  - Stacked Bar Chart: Alert Status by `risk_category` (Open vs Under Investigation vs Resolved).

### Page 2: Transaction Volume & Anomaly Trends
- **Area Chart**: Total Transaction Amount vs Flagged Amount over `transactions[timestamp]`.
- **Clustered Column Chart**: Transaction Count by `transactions[channel]` (Online, Mobile App, POS, ATM, Branch).
- **Matrix Table**: Transactions grouped by `location_country` and `location_city`.

### Page 3: Detection Rule Effectiveness
- **Horizontal Bar Chart**: Count of triggers by `fraud_rules[rule_name]`.
- **Scatter Plot**: Implied velocity (km/h) vs Distance (km) for geographic anomaly evaluation.
- **Treemap**: Alert volume by `merchant_category`.

---

## 5. Security & Credential Best Practices

1. **Never Save Passwords in Shared `.pbix` Files**:
   - Power BI Desktop caches credentials in Windows Credential Manager under the current Windows user profile.
   - Do not commit `.pbix` files with sensitive connection strings to public GitHub repositories.
2. **Read-Only Database User**:
   - For corporate environments, create a dedicated read-only MySQL user:
     ```sql
     CREATE USER 'powerbi_reader'@'localhost' IDENTIFIED BY 'SafePasswordHere';
     GRANT SELECT ON banking_fraud_monitoring.* TO 'powerbi_reader'@'localhost';
     FLUSH PRIVILEGES;
     ```
