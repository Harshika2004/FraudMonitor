from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.analytics.aggregator import AnalyticsAggregator
from backend.app.schemas.analytics import DashboardAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_data(
    days: int = Query(0, ge=0, le=3650, description="Lookback window in days (0 = all transactions)"),
    dataset_id: Optional[int] = Query(None, description="Dataset ID to filter analytics"),
    db: Session = Depends(get_db)
):
    """Retrieve full dashboard KPI cards, risk distribution, trends, and rule effectiveness stats."""
    return AnalyticsAggregator.get_dashboard_analytics(db=db, days=days, dataset_id=dataset_id)
