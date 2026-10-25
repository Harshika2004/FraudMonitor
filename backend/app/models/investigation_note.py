from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    note_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False, index=True)
    author = Column(String(60), nullable=False, default="Risk Analyst")
    note_text = Column(Text, nullable=False)
    action_taken = Column(String(60), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    alert = relationship("Alert", back_populates="notes")

    def __repr__(self):
        return f"<InvestigationNote Alert={self.alert_id} Author={self.author}>"
