import sqlite3

conn = sqlite3.connect("banking_fraud.db")
c = conn.cursor()

# 1. Check if transactions already has the new columns
c.execute("PRAGMA table_info(transactions)")
tx_cols = [row[1] for row in c.fetchall()]

new_tx_cols = [
    ("customer_name", "VARCHAR(100)"),
    ("email", "VARCHAR(100)"),
    ("customer_ref", "VARCHAR(50)"),
    ("account_ref", "VARCHAR(50)"),
    ("account_balance", "NUMERIC(15, 2)")
]
for col_name, col_type in new_tx_cols:
    if col_name not in tx_cols:
        c.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
        print(f"Added column {col_name} to transactions")

# 2. Check if accounts already has the new columns
c.execute("PRAGMA table_info(accounts)")
acc_cols = [row[1] for row in c.fetchall()]

# Recreate accounts table to make customer_id and current_balance nullable and add new cols
c.execute("DROP INDEX IF EXISTS ix_accounts_account_number")
c.execute("DROP INDEX IF EXISTS ix_accounts_account_id")
c.execute("DROP INDEX IF EXISTS ix_accounts_customer_id")

c.execute("""
CREATE TABLE IF NOT EXISTS accounts_new (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number VARCHAR(50) NOT NULL,
    customer_id INTEGER NULL,
    account_type VARCHAR(30) NOT NULL DEFAULT 'CHECKING',
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    current_balance NUMERIC(15, 2) NULL,
    average_monthly_balance NUMERIC(15, 2) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dataset_id INTEGER NULL,
    customer_name VARCHAR(100) NULL,
    email VARCHAR(100) NULL,
    customer_ref VARCHAR(50) NULL
)
""")

c.execute("""
INSERT INTO accounts_new (account_id, account_number, customer_id, account_type, currency, current_balance, average_monthly_balance, status, created_at, updated_at)
SELECT account_id, account_number, customer_id, account_type, currency, current_balance, average_monthly_balance, status, created_at, updated_at
FROM accounts
""")

c.execute("DROP TABLE accounts")
c.execute("ALTER TABLE accounts_new RENAME TO accounts")
c.execute("CREATE INDEX IF NOT EXISTS ix_accounts_dataset_acc ON accounts(dataset_id, account_number)")
c.execute("CREATE INDEX IF NOT EXISTS ix_accounts_account_id ON accounts(account_id)")
print("Migrated accounts table successfully")

# 3. Migrate customers table
c.execute("DROP INDEX IF EXISTS ix_customers_customer_ref")
c.execute("DROP INDEX IF EXISTS ix_customers_customer_id")

c.execute("""
CREATE TABLE IF NOT EXISTS customers_new (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_ref VARCHAR(50) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL DEFAULT '',
    email VARCHAR(100) NULL,
    phone VARCHAR(25) NULL,
    risk_segment VARCHAR(30) NOT NULL DEFAULT 'STANDARD',
    account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dataset_id INTEGER NULL
)
""")

c.execute("""
INSERT INTO customers_new (customer_id, customer_ref, first_name, last_name, email, phone, risk_segment, account_status, created_at, updated_at)
SELECT customer_id, customer_ref, first_name, last_name, email, phone, risk_segment, account_status, created_at, updated_at
FROM customers
""")

c.execute("DROP TABLE customers")
c.execute("ALTER TABLE customers_new RENAME TO customers")
c.execute("CREATE INDEX IF NOT EXISTS ix_customers_dataset_ref ON customers(dataset_id, customer_ref)")
c.execute("CREATE INDEX IF NOT EXISTS ix_customers_customer_id ON customers(customer_id)")
print("Migrated customers table successfully")

# Backfill dataset_id=1 on existing seed customers and accounts
c.execute("UPDATE customers SET dataset_id = 1 WHERE dataset_id IS NULL")
c.execute("UPDATE accounts SET dataset_id = 1 WHERE dataset_id IS NULL")

conn.commit()

# Verify counts
c.execute("SELECT COUNT(*) FROM customers")
print("Customers count:", c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM accounts")
print("Accounts count:", c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM transactions")
print("Transactions count:", c.fetchone()[0])

conn.close()
print("All migrations completed successfully!")
