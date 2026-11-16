"""Migration: add customer_category column to transactions and accounts tables."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "banking_fraud.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(transactions)")
t_cols = [r[1] for r in cur.fetchall()]
cur.execute("PRAGMA table_info(accounts)")
a_cols = [r[1] for r in cur.fetchall()]

print("transactions cols:", t_cols)
print("accounts cols:", a_cols)

if "customer_category" not in t_cols:
    cur.execute("ALTER TABLE transactions ADD COLUMN customer_category VARCHAR(100)")
    print("Added customer_category to transactions")
else:
    print("customer_category already exists in transactions")

if "customer_category" not in a_cols:
    cur.execute("ALTER TABLE accounts ADD COLUMN customer_category VARCHAR(100)")
    print("Added customer_category to accounts")
else:
    print("customer_category already exists in accounts")

conn.commit()
conn.close()
print("Migration complete.")
