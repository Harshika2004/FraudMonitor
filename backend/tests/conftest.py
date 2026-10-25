import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.database.base import Base
from backend.app.database.connection import get_db
from backend.app.main import app
from backend.app.models.customer import Customer
from backend.app.models.account import Account
from backend.app.models.transaction import Transaction
from backend.app.models.rule import FraudRule
from backend.app.models.risk_config import RiskScoreConfiguration
from backend.app.models.alert import Alert, AlertRuleTrigger
from database.seed_data import seed_rules_and_bands

# Isolated in-memory SQLite database for testing with StaticPool so all sessions share the DB
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

@pytest.fixture(scope="function")
def db_session():
    """Provides a pristine database session for each test function."""
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    seed_rules_and_bands(db)

    # Seed base customer and account for test transactions
    cust = Customer(
        customer_ref="TEST-CUST-001",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@synthetic.test",
        phone="+1-555-9999",
        risk_segment="STANDARD",
        account_status="ACTIVE"
    )
    db.add(cust)
    db.commit()
    db.refresh(cust)

    acct = Account(
        account_number="ACCT-TEST-1234",
        customer_id=cust.customer_id,
        account_type="CHECKING",
        currency="USD",
        current_balance=Decimal("15000.00"),
        status="ACTIVE"
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine_test)

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
