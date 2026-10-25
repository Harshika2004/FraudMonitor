from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_ref = Column(String(50), unique=True, nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.transaction_id", ondelete="CASCADE"), unique=True, nullable=False)
    risk_score = Column(Integer, nullable=False, index=True)
    risk_category = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(30), nullable=False, default="OPEN", index=True)  # OPEN, UNDER_INVESTIGATION, RESOLVED
    resolution_reason = Column(String(50), nullable=True)  # FALSE_POSITIVE, CONFIRMED_SUSPICIOUS, CUSTOMER_VERIFIED, ESCALATED
    assigned_to = Column(String(60), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    transaction = relationship("Transaction", back_populates="alert")
    triggers = relationship("AlertRuleTrigger", back_populates="alert", cascade="all, delete-orphan")
    notes = relationship("InvestigationNote", back_populates="alert", cascade="all, delete-orphan", order_by="desc(InvestigationNote.created_at)")

    def __repr__(self):
        return f"<Alert {self.alert_ref} Score={self.risk_score} Category={self.risk_category} Status={self.status}>"


class AlertRuleTrigger(Base):
    __tablename__ = "alert_rule_triggers"

    trigger_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("fraud_rules.rule_id", ondelete="RESTRICT"), nullable=False, index=True)
    rule_code = Column(String(50), nullable=False)
    rule_name = Column(String(100), nullable=False)
    points_awarded = Column(Integer, nullable=False)
    trigger_reason = Column(Text, nullable=False)
    evaluation_context_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    alert = relationship("Alert", back_populates="triggers")
    rule = relationship("FraudRule", back_populates="triggers")

    def __repr__(self):
        return f"<Trigger Alert={self.alert_id} Rule={self.rule_code} Pts={self.points_awarded}>"
