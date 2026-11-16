from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_number = Column(String(50), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=True, index=True)
    customer_name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    customer_ref = Column(String(50), nullable=True)
    customer_category = Column(String(100), nullable=True)
    account_type = Column(String(30), nullable=False, default="CHECKING")  # SAVINGS, CHECKING, CREDIT, BUSINESS
    currency = Column(String(3), nullable=False, default="USD")
    current_balance = Column(Numeric(15, 2), nullable=True, default=None)
    average_monthly_balance = Column(Numeric(15, 2), nullable=True, default=None)
    status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, DORMANT, FROZEN, CLOSED
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account {self.account_number} (Dataset {self.dataset_id})>"
