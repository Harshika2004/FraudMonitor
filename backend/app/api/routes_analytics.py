from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.analytics.aggregator import AnalyticsAggregator
from backend.app.schemas.analytics import DashboardAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_data(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days for time-series charts"),
    db: Session = Depends(get_db)
):
    """Retrieve full dashboard KPI cards, risk distribution, trends, and rule effectiveness stats."""
    return AnalyticsAggregator.get_dashboard_analytics(db=db, days=days)
