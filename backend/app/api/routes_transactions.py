from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.services.transaction_service import TransactionService
from backend.app.schemas.transaction import (
    TransactionOut,
    TransactionListResponse,
    TransactionCreate,
    SingleTransactionEvaluationResponse,
    BatchEvaluationResponse
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page"),
    account_id: Optional[int] = Query(None, description="Filter by Account ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by type (e.g. TRANSFER, WITHDRAWAL)"),
    channel: Optional[str] = Query(None, description="Filter by channel (e.g. ONLINE, ATM)"),
    min_amount: Optional[Decimal] = Query(None, ge=0, description="Minimum transaction amount"),
    max_amount: Optional[Decimal] = Query(None, ge=0, description="Maximum transaction amount"),
    start_date: Optional[datetime] = Query(None, description="Start timestamp filter"),
    end_date: Optional[datetime] = Query(None, description="End timestamp filter"),
    is_evaluated: Optional[bool] = Query(None, description="Filter by evaluation status"),
    risk_category: Optional[str] = Query(None, description="Filter by risk category (LOW, MEDIUM, HIGH, CRITICAL)"),
    search: Optional[str] = Query(None, description="Search transaction ref, account, customer, or city"),
    sort_by: str = Query("timestamp", description="Sort column (timestamp, amount, transaction_id)"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """Retrieve paginated transactions with multi-criteria filtering and sorting."""
    total, items = TransactionService.get_transactions(
        db=db,
        page=page,
        page_size=page_size,
        account_id=account_id,
        transaction_type=transaction_type,
        channel=channel,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        is_evaluated=is_evaluated,
        risk_category=risk_category,
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

@router.get("/{transaction_id}")
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of a transaction and its associated account and customer."""
    data = TransactionService.get_transaction_by_id(db, transaction_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found."
        )

    txn = data["transaction"]
    acct = data["account"]
    cust = data["customer"]
    alert = data["alert"]

    return {
        "transaction": {
            "transaction_id": txn.transaction_id,
            "transaction_ref": txn.transaction_ref,
            "account_id": txn.account_id,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "transaction_type": txn.transaction_type,
            "channel": txn.channel,
            "timestamp": txn.timestamp.isoformat(),
            "location_city": txn.location_city,
            "location_country": txn.location_country,
            "latitude": float(txn.latitude) if txn.latitude else None,
            "longitude": float(txn.longitude) if txn.longitude else None,
            "device_id": txn.device_id,
            "ip_address": txn.ip_address,
            "merchant_name": txn.merchant_name,
            "merchant_category": txn.merchant_category,
            "status": txn.status,
            "is_evaluated": txn.is_evaluated,
            "evaluated_at": txn.evaluated_at.isoformat() if txn.evaluated_at else None,
            "created_at": txn.created_at.isoformat()
        },
        "account": {
            "account_id": acct.account_id,
            "account_number": acct.account_number,
            "account_type": acct.account_type,
            "current_balance": float(acct.current_balance),
            "status": acct.status
        },
        "customer": {
            "customer_id": cust.customer_id,
            "customer_ref": cust.customer_ref,
            "name": f"{cust.first_name} {cust.last_name}",
            "email": cust.email,
            "risk_segment": cust.risk_segment
        },
        "alert": {
            "alert_id": alert.alert_id,
            "alert_ref": alert.alert_ref,
            "risk_score": alert.risk_score,
            "risk_category": alert.risk_category,
            "status": alert.status
        } if alert else None
    }

@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    """Add a new transaction and queue it for rule evaluation."""
    txn = TransactionService.create_transaction(db, payload)
    return {
        "message": "Transaction created successfully.",
        "transaction_id": txn.transaction_id,
        "transaction_ref": txn.transaction_ref
    }

@router.post("/import-csv")
async def import_csv_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import synthetic transactions from a CSV file with validation."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a CSV file."
        )

    content_bytes = await file.read()
    content_str = content_bytes.decode("utf-8", errors="replace")
    result = TransactionService.import_transactions_from_csv(db, content_str)
    return result

@router.post("/{transaction_id}/evaluate", response_model=SingleTransactionEvaluationResponse)
def evaluate_single_transaction(
    transaction_id: int,
    force_reevaluate: bool = Query(False, description="Re-run evaluation even if previously evaluated"),
    db: Session = Depends(get_db)
):
    """Execute rule evaluation on a specific transaction."""
    try:
        return TransactionService.evaluate_transaction(db, transaction_id, force_reevaluate=force_reevaluate)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Evaluation failed: {str(e)}")

@router.post("/evaluate-batch", response_model=BatchEvaluationResponse)
def evaluate_batch(
    only_unevaluated: bool = Query(True, description="Only evaluate uninspected transactions"),
    limit: Optional[int] = Query(None, ge=1, description="Maximum transactions to evaluate in batch (omit or null to evaluate all)"),
    db: Session = Depends(get_db)
):
    """Batch-evaluates transactions against all enabled detection rules."""
    return TransactionService.batch_evaluate(db, only_unevaluated=only_unevaluated, limit=limit)
