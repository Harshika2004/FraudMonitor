from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database.connection import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.customer import Customer
from backend.app.models.account import Account
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert
from backend.app.rules.engine import rule_engine

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("")
def list_customers(
    search: Optional[str] = Query(None, description="Search customer name, email, or identifier"),
    dataset_id: Optional[int] = Query(None, description="Dataset ID to scope query"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    List dataset-scoped directory profiles.
    - If customer_id was present in CSV: returns mode='CUSTOMER', title='Customer Directory',
      grouped by distinct customer with distinct account counts.
    - If customer_id was missing: returns mode='ACCOUNT', title='Account Directory',
      displaying distinct account-level profiles with Accounts column omitted.
    """
    actual_limit = limit if isinstance(limit, int) else 100
    actual_search = search if isinstance(search, str) else None
    actual_dataset_id = dataset_id if isinstance(dataset_id, int) else None

    if actual_dataset_id is None:
        active_ds = db.query(Dataset).filter(Dataset.is_active == True).first()
        if active_ds:
            actual_dataset_id = active_ds.dataset_id

    if actual_dataset_id is None:
        return {
            "mode": "CUSTOMER",
            "title": "Customer Directory",
            "has_balance": False,
            "items": []
        }

    dataset_id = actual_dataset_id
    search = actual_search
    limit = actual_limit

    cust_count = db.query(func.count(Customer.customer_id)).filter(Customer.dataset_id == dataset_id).scalar() or 0
    has_balance = db.query(Account).filter(
        Account.dataset_id == dataset_id,
        Account.current_balance.isnot(None)
    ).first() is not None

    if cust_count > 0:
        mode = "CUSTOMER"
        title = "Customer Directory"
        query = db.query(Customer).filter(Customer.dataset_id == dataset_id)
        if search:
            pat = f"%{search}%"
            query = query.filter(
                (Customer.customer_ref.ilike(pat)) |
                (Customer.first_name.ilike(pat)) |
                (Customer.last_name.ilike(pat)) |
                (Customer.email.ilike(pat))
            )
        customers = query.order_by(Customer.customer_id.asc()).limit(limit).all()

        items = []
        for c in customers:
            accts = db.query(Account).filter(
                Account.customer_id == c.customer_id,
                Account.dataset_id == dataset_id
            ).all()
            acct_ids = [a.account_id for a in accts]

            txn_cnt = 0
            alert_cnt = 0
            max_score = 0
            if acct_ids:
                txn_cnt = db.query(func.count(Transaction.transaction_id)).filter(
                    Transaction.dataset_id == dataset_id,
                    Transaction.account_id.in_(acct_ids)
                ).scalar() or 0

                alert_rows = db.query(Alert.risk_score).join(
                    Transaction, Alert.transaction_id == Transaction.transaction_id
                ).filter(
                    Transaction.dataset_id == dataset_id,
                    Transaction.account_id.in_(acct_ids)
                ).all()

                alert_cnt = len(alert_rows)
                if alert_rows:
                    max_score = max([r[0] for r in alert_rows])

            risk_cat = rule_engine.determine_risk_category(max_score)

            # Name and email handling:
            # If customer_name exists, display actual value; if missing, "Not provided"
            raw_name = f"{c.first_name} {c.last_name}".strip()
            if not raw_name or raw_name == "Not provided":
                disp_name = c.first_name or "Not provided"
            else:
                disp_name = raw_name

            disp_email = c.email if (c.email and c.email != "Not provided") else "Not provided"

            total_bal = None
            if has_balance:
                total_bal = sum([float(a.current_balance) for a in accts if a.current_balance is not None])

            items.append({
                "id": c.customer_id,
                "identifier": c.customer_ref,
                "name": disp_name,
                "email": disp_email,
                "customer_category": accts[0].customer_category if accts and accts[0].customer_category else "Not provided",
                "account_count": len(accts),
                "transaction_count": txn_cnt,
                "alert_count": alert_cnt,
                "risk_score": max_score,
                "risk_segment": risk_cat,
                "has_balance": has_balance,
                "total_balance": round(total_bal, 2) if total_bal is not None else None,
                "created_at": c.created_at.isoformat() if c.created_at else None
            })

        return {
            "mode": mode,
            "title": title,
            "has_balance": has_balance,
            "items": items
        }

    else:
        # Account-level directory mode
        mode = "ACCOUNT"
        title = "Account Directory"
        query = db.query(Account).filter(Account.dataset_id == dataset_id)
        if search:
            pat = f"%{search}%"
            query = query.filter(
                (Account.account_number.ilike(pat)) |
                (Account.customer_name.ilike(pat)) |
                (Account.email.ilike(pat))
            )
        accounts = query.order_by(Account.account_id.asc()).limit(limit).all()

        items = []
        for a in accounts:
            txn_cnt = db.query(func.count(Transaction.transaction_id)).filter(
                Transaction.dataset_id == dataset_id,
                Transaction.account_id == a.account_id
            ).scalar() or 0

            alert_rows = db.query(Alert.risk_score).join(
                Transaction, Alert.transaction_id == Transaction.transaction_id
            ).filter(
                Transaction.dataset_id == dataset_id,
                Transaction.account_id == a.account_id
            ).all()

            alert_cnt = len(alert_rows)
            max_score = max([r[0] for r in alert_rows], default=0)
            risk_cat = rule_engine.determine_risk_category(max_score)

            disp_name = a.customer_name if a.customer_name else "Not provided"
            disp_email = a.email if a.email else "Not provided"
            total_bal = float(a.current_balance) if a.current_balance is not None else None

            items.append({
                "id": a.account_id,
                "identifier": a.account_number,
                "name": disp_name,
                "email": disp_email,
                "customer_category": a.customer_category if a.customer_category else "Not provided",
                "account_count": None,  # No accounts column in Account mode
                "transaction_count": txn_cnt,
                "alert_count": alert_cnt,
                "risk_score": max_score,
                "risk_segment": risk_cat,
                "has_balance": has_balance,
                "total_balance": round(total_bal, 2) if total_bal is not None else None,
                "created_at": a.created_at.isoformat() if a.created_at else None
            })

        return {
            "mode": mode,
            "title": title,
            "has_balance": has_balance,
            "items": items
        }

@router.get("/{entity_id}")
def get_entity_details(
    entity_id: int,
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve detailed customer or account profile, linked accounts, recent transactions, and alert history."""
    # Check if customer exists first (unless mode == 'ACCOUNT')
    c = None
    if mode != "ACCOUNT":
        c = db.query(Customer).filter(Customer.customer_id == entity_id).first()

    if c:
        accounts = db.query(Account).filter(Account.customer_id == c.customer_id).all()
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

        raw_name = f"{c.first_name} {c.last_name}".strip()
        disp_name = c.first_name if (not raw_name or raw_name == "Not provided") else raw_name
        max_score = max([a["risk_score"] for a in alerts], default=0)

        return {
            "mode": "CUSTOMER",
            "profile": {
                "id": c.customer_id,
                "identifier": c.customer_ref,
                "name": disp_name,
                "email": c.email or "Not provided",
                "phone": c.phone or "Not provided",
                "risk_segment": rule_engine.determine_risk_category(max_score),
                "account_status": c.account_status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            },
            "accounts": [
                {
                    "account_id": a.account_id,
                    "account_number": a.account_number,
                    "account_type": a.account_type,
                    "currency": a.currency,
                    "current_balance": float(a.current_balance) if a.current_balance is not None else None,
                    "status": a.status
                }
                for a in accounts
            ],
            "recent_transactions": recent_txs,
            "alerts": alerts
        }

    # Otherwise, try looking up as Account
    a = db.query(Account).filter(Account.account_id == entity_id).first()
    if not a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID {entity_id} not found."
        )

    txs = (
        db.query(Transaction)
        .filter(Transaction.account_id == a.account_id)
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
        .filter(Transaction.account_id == a.account_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    alerts = [
        {
            "alert_id": alt[0].alert_id,
            "alert_ref": alt[0].alert_ref,
            "transaction_ref": alt[1],
            "amount": float(alt[2]),
            "risk_score": alt[0].risk_score,
            "risk_category": alt[0].risk_category,
            "status": alt[0].status,
            "created_at": alt[0].created_at.isoformat()
        }
        for alt in alt_records
    ]

    max_score = max([alt["risk_score"] for alt in alerts], default=0)

    return {
        "mode": "ACCOUNT",
        "profile": {
            "id": a.account_id,
            "identifier": a.account_number,
            "name": a.customer_name or "Not provided",
            "email": a.email or "Not provided",
            "phone": "Not provided",
            "risk_segment": rule_engine.determine_risk_category(max_score),
            "account_status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None
        },
        "accounts": [
            {
                "account_id": a.account_id,
                "account_number": a.account_number,
                "account_type": a.account_type,
                "currency": a.currency,
                "current_balance": float(a.current_balance) if a.current_balance is not None else None,
                "status": a.status
            }
        ],
        "recent_transactions": recent_txs,
        "alerts": alerts
    }
