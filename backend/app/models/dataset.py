from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, func
from sqlalchemy.orm import relationship
from backend.app.database.base import Base

class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    total_rows = Column(Integer, nullable=False, default=0)
    total_columns = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    status = Column(String(50), nullable=False, default="UPLOADED")  # UPLOADED, ANALYSED, FAILED
    created_at = Column(DateTime, nullable=False, default=func.now())
    analyzed_at = Column(DateTime, nullable=True)

    transactions = relationship("Transaction", back_populates="dataset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dataset {self.dataset_id} {self.filename} status={self.status} active={self.is_active}>"
