from sqlalchemy import Column, Integer, String
from backend.app.database.base import Base

class RiskScoreConfiguration(Base):
    __tablename__ = "risk_score_configurations"

    config_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category_name = Column(String(20), unique=True, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    min_score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    color_hex = Column(String(10), nullable=False)
    description = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<RiskScoreConfig {self.category_name} [{self.min_score}-{self.max_score}]>"
