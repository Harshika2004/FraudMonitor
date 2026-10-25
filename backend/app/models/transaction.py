from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_ref = Column(String(50), unique=True, nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False, index=True)
    currency = Column(String(3), nullable=False, default="USD")
    transaction_type = Column(String(30), nullable=False, default="TRANSFER")  # TRANSFER, DEPOSIT, WITHDRAWAL, CARD_PAYMENT, ONLINE_PURCHASE
    channel = Column(String(30), nullable=False, default="ONLINE")  # ATM, BRANCH, ONLINE, MOBILE_APP, POS
    timestamp = Column(DateTime, nullable=False, index=True)
    location_city = Column(String(60), nullable=False)
    location_country = Column(String(60), nullable=False, default="USA")
    latitude = Column(Numeric(10, 6), nullable=True)
    longitude = Column(Numeric(10, 6), nullable=True)
    device_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    merchant_name = Column(String(100), nullable=True)
    merchant_category = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="COMPLETED")  # COMPLETED, PENDING, REVERSED, FAILED
    is_evaluated = Column(Boolean, nullable=False, default=False, index=True)
    evaluated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    account = relationship("Account", back_populates="transactions")
    alert = relationship("Alert", back_populates="transaction", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transaction {self.transaction_ref} Amount={self.amount} {self.currency}>"
