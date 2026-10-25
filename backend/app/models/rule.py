from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class FraudRule(Base):
    __tablename__ = "fraud_rules"

    rule_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_code = Column(String(50), unique=True, nullable=False, index=True)
    rule_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    rule_type = Column(String(50), nullable=False)  # THRESHOLD, FREQUENCY, TEMPORAL, GEOGRAPHIC, STATISTICAL
    parameters_json = Column(JSON, nullable=False)
    risk_points = Column(Integer, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    triggers = relationship("AlertRuleTrigger", back_populates="rule")

    def __repr__(self):
        return f"<FraudRule {self.rule_code} Enabled={self.is_enabled} Points={self.risk_points}>"
