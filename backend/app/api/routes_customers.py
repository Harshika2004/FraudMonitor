from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database.connection import get_db
from backend.app.models.customer import Customer
from backend.app.models.account import Account
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("")
def list_customers(
    search: Optional[str] = Query(None, description="Search customer name or reference"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List synthetic customers with aggregate account counts and alert summary."""
    query = db.query(Customer)
    if search:
        pat = f"%{search}%"
        query = query.filter(
            (Customer.customer_ref.like(pat)) |
            (Customer.first_name.like(pat)) |
            (Customer.last_name.like(pat)) |
            (Customer.email.like(pat))
        )

    customers = query.order_by(Customer.customer_id.asc()).limit(limit).all()

    result = []
    for c in customers:
        accts = db.query(Account).filter(Account.customer_id == c.customer_id).all()
        acct_ids = [a.account_id for a in accts]
        alert_cnt = (
            db.query(func.count(Alert.alert_id))
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .filter(Transaction.account_id.in_(acct_ids))
            .scalar() or 0
        ) if acct_ids else 0

        total_balance = sum([float(a.current_balance) for a in accts])

        result.append({
            "customer_id": c.customer_id,
            "customer_ref": c.customer_ref,
            "name": f"{c.first_name} {c.last_name}",
            "email": c.email,
            "phone": c.phone,
            "risk_segment": c.risk_segment,
            "account_status": c.account_status,
            "account_count": len(accts),
            "total_balance": round(total_balance, 2),
            "alert_count": alert_cnt,
            "created_at": c.created_at.isoformat()
        })

    return result

@router.get("/{customer_id}")
def get_customer_details(customer_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed customer profile, linked accounts, recent transactions, and alert history."""
    c = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found."
        )

    accounts = db.query(Account).filter(Account.customer_id == customer_id).all()
    acct_ids = [a.account_id for a in accounts]

    recent_txs = []
    alerts = []

    if acct_ids:
        txs = (
            db.query(Transaction)
            .filter(Transaction.account_id.in_(acct_ids))
            .order_by(Transaction.timestamp.desc())
            .limit(20)
            .all()
        )
        recent_txs = [
            {
                "transaction_id": t.transaction_id,
                "transaction_ref": t.transaction_ref,
                "amount": float(t.amount),
                "transaction_type": t.transaction_type,
                "timestamp": t.timestamp.isoformat(),
                "location_city": t.location_city,
                "channel": t.channel,
                "is_evaluated": t.is_evaluated
            }
            for t in txs
        ]

        alt_records = (
            db.query(Alert, Transaction.transaction_ref, Transaction.amount)
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .filter(Transaction.account_id.in_(acct_ids))
            .order_by(Alert.created_at.desc())
            .all()
        )
        alerts = [
            {
                "alert_id": a[0].alert_id,
                "alert_ref": a[0].alert_ref,
                "transaction_ref": a[1],
                "amount": float(a[2]),
                "risk_score": a[0].risk_score,
                "risk_category": a[0].risk_category,
                "status": a[0].status,
                "created_at": a[0].created_at.isoformat()
            }
            for a in alt_records
        ]

    return {
        "customer": {
            "customer_id": c.customer_id,
            "customer_ref": c.customer_ref,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "phone": c.phone,
            "risk_segment": c.risk_segment,
            "account_status": c.account_status,
            "created_at": c.created_at.isoformat()
        },
        "accounts": [
            {
                "account_id": a.account_id,
                "account_number": a.account_number,
                "account_type": a.account_type,
                "currency": a.currency,
                "current_balance": float(a.current_balance),
                "status": a.status
            }
            for a in accounts
        ],
        "recent_transactions": recent_txs,
        "alerts": alerts
    }
