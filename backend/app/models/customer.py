from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_ref = Column(String(50), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, default="")
    email = Column(String(100), nullable=True)
    phone = Column(String(25), nullable=True)
    risk_segment = Column(String(30), nullable=False, default="STANDARD")  # LOW_RISK, STANDARD, HIGH_NET_WORTH
    account_status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED, CLOSED
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    accounts = relationship("Account", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.customer_ref}: {self.first_name} {self.last_name}>"
