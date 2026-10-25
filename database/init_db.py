"""
Database Initialization & Setup Script
Creates database tables using SQLAlchemy models and executes seed data population.
Can be executed against MySQL or SQLite.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.database.connection import engine, SessionLocal
from backend.app.database.base import Base
import backend.app.models  # Load all models into SQLAlchemy metadata
from database.seed_data import seed_database

def init_database():
    db_url = settings.get_database_url()
    print("=" * 70)
    print("  Initializing Banking Fraud Monitoring Database Schema")
    print(f"  Target Database URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print("=" * 70)

    try:
        # If targeting MySQL, ensure the database exists prior to metadata creation
        if not db_url.startswith("sqlite"):
            try:
                import pymysql
                conn = pymysql.connect(
                    host=settings.DB_HOST,
                    port=settings.DB_PORT,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD,
                    charset="utf8mb4"
                )
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                conn.commit()
                conn.close()
                print(f"[SUCCESS] MySQL database `{settings.DB_NAME}` verified/created.")
            except Exception as my_err:
                print(f"[WARNING] Could not auto-create database with root: {my_err}")

        print("[1/2] Creating database schema tables...")
        Base.metadata.create_all(bind=engine)
        print("[SUCCESS] All tables (customers, accounts, transactions, fraud_rules, alerts, etc.) verified/created.")

        print("[2/2] Running synthetic sample data generation...")
        seed_database(evaluate_alerts=True)
        print("\n[COMPLETE] Database initialization and synthetic seeding succeeded!")
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. If using MySQL, verify MySQL80 service is running: Get-Service -Name MySQL80")
        print("2. Ensure your password in backend/.env matches your local MySQL root password.")
        print("3. Ensure the database exists: CREATE DATABASE IF NOT EXISTS banking_fraud_monitoring;")
        print("4. Or set DB_URL=sqlite:///./banking_fraud.db in backend/.env for portable local execution.")
        sys.exit(1)

if __name__ == "__main__":
    init_database()
