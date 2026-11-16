import sqlite3

conn = sqlite3.connect("banking_fraud.db")
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name='accounts'")
print("ACCOUNTS SQL:")
print(c.fetchone()[0])

c.execute("SELECT sql FROM sqlite_master WHERE name='customers'")
print("\nCUSTOMERS SQL:")
print(c.fetchone()[0])

c.execute("SELECT sql FROM sqlite_master WHERE name='transactions'")
print("\nTRANSACTIONS SQL:")
print(c.fetchone()[0])
conn.close()
