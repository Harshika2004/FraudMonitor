import sqlite3

conn = sqlite3.connect("banking_fraud.db")
try:
    conn.execute("INSERT INTO accounts (account_number, customer_id, account_type, currency, current_balance, status, created_at, updated_at) VALUES ('TEST_ACC_NULL', NULL, 'CHECKING', 'USD', 0.0, 'ACTIVE', datetime('now'), datetime('now'))")
    print("SUCCESS inserting with customer_id=NULL")
    conn.rollback()
except Exception as e:
    print("Error with NULL:", e)
conn.close()
