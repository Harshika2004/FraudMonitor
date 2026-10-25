from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.services.alert_service import AlertService
from backend.app.schemas.alert import (
    AlertOut,
    AlertDetailOut,
    AlertListResponse,
    AlertStatusUpdate,
    InvestigationNoteCreate,
    InvestigationNoteOut
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("", response_model=AlertListResponse)
def list_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page"),
    risk_category: Optional[str] = Query(None, description="Filter by risk category (LOW, MEDIUM, HIGH, CRITICAL)"),
    status: Optional[str] = Query(None, description="Filter by alert status (OPEN, UNDER_INVESTIGATION, RESOLVED)"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum risk score threshold"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    search: Optional[str] = Query(None, description="Search alert ref, transaction, or customer"),
    sort_by: str = Query("created_at", description="Sort by created_at, risk_score, or amount"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    db: Session = Depends(get_db)
):
    """Retrieve filtered, sorted, paginated alert investigation queue."""
    total, items = AlertService.get_alerts(
        db=db,
        page=page,
        page_size=page_size,
        risk_category=risk_category,
        status=status,
        min_score=min_score,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

@router.get("/{alert_id}", response_model=AlertDetailOut)
def get_alert_detail(alert_id: int, db: Session = Depends(get_db)):
    """Retrieve complete dossier for an alert: linked transaction, triggered rules, and investigation history."""
    detail = AlertService.get_alert_detail(db, alert_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found."
        )
    return detail

@router.patch("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update alert status (e.g. Open -> Under Investigation -> Resolved) and record audit log."""
    try:
        updated = AlertService.update_alert_status(db, alert_id, payload)
        return {
            "message": "Alert status updated successfully.",
            "alert_id": updated.alert_id,
            "status": updated.status,
            "resolution_reason": updated.resolution_reason,
            "updated_at": updated.updated_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{alert_id}/notes", response_model=InvestigationNoteOut, status_code=status.HTTP_201_CREATED)
def add_investigation_note(
    alert_id: int,
    payload: InvestigationNoteCreate,
    db: Session = Depends(get_db)
):
    """Append an analyst note to the alert investigation file."""
    try:
        return AlertService.add_investigation_note(db, alert_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
