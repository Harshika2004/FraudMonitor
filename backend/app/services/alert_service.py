import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from backend.app.models.alert import Alert, AlertRuleTrigger
from backend.app.models.transaction import Transaction
from backend.app.models.account import Account
from backend.app.models.customer import Customer
from backend.app.models.investigation_note import InvestigationNote
from backend.app.schemas.alert import AlertStatusUpdate, InvestigationNoteCreate

logger = logging.getLogger(__name__)

class AlertService:

    @staticmethod
    def get_alerts(
        db: Session,
        page: int = 1,
        page_size: int = 25,
        risk_category: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_score: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Query alerts with filtering, sorting, and linked transaction context."""
        query = (
            db.query(
                Alert,
                Transaction.transaction_ref,
                Transaction.amount,
                Transaction.currency,
                Transaction.transaction_type,
                Transaction.channel,
                Transaction.timestamp,
                Transaction.location_city,
                Account.account_number,
                Customer.customer_ref,
                Customer.first_name,
                Customer.last_name
            )
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .join(Account, Transaction.account_id == Account.account_id)
            .join(Customer, Account.customer_id == Customer.customer_id)
        )

        if risk_category:
            query = query.filter(Alert.risk_category == risk_category)
        if status:
            query = query.filter(Alert.status == status)
        if min_score is not None:
            query = query.filter(Alert.risk_score >= min_score)
        if start_date:
            query = query.filter(Alert.created_at >= start_date)
        if end_date:
            query = query.filter(Alert.created_at <= end_date)
        if search:
            search_pat = f"%{search}%"
            query = query.filter(
                (Alert.alert_ref.like(search_pat)) |
                (Transaction.transaction_ref.like(search_pat)) |
                (Account.account_number.like(search_pat)) |
                (Customer.first_name.like(search_pat)) |
                (Customer.last_name.like(search_pat))
            )

        total = query.count()

        sort_column = getattr(Alert, sort_by, Alert.created_at)
        if sort_by == "amount":
            sort_column = Transaction.amount

        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        items = []
        for row in results:
            alt = row[0]
            items.append({
                "alert_id": alt.alert_id,
                "alert_ref": alt.alert_ref,
                "transaction_id": alt.transaction_id,
                "risk_score": alt.risk_score,
                "risk_category": alt.risk_category,
                "status": alt.status,
                "resolution_reason": alt.resolution_reason,
                "assigned_to": alt.assigned_to,
                "created_at": alt.created_at,
                "updated_at": alt.updated_at,
                "transaction_ref": row[1],
                "amount": row[2],
                "currency": row[3],
                "transaction_type": row[4],
                "channel": row[5],
                "transaction_timestamp": row[6],
                "location_city": row[7],
                "account_number": row[8],
                "customer_ref": row[9],
                "customer_name": f"{row[10]} {row[11]}"
            })

        return total, items

    @staticmethod
    def get_alert_detail(db: Session, alert_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve complete alert investigation dossier with triggers and audit notes."""
        result = (
            db.query(
                Alert,
                Transaction,
                Account,
                Customer
            )
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .join(Account, Transaction.account_id == Account.account_id)
            .join(Customer, Account.customer_id == Customer.customer_id)
            .filter(Alert.alert_id == alert_id)
            .first()
        )

        if not result:
            return None

        alt, txn, acct, cust = result
        triggers = (
            db.query(AlertRuleTrigger)
            .filter(AlertRuleTrigger.alert_id == alert_id)
            .order_by(desc(AlertRuleTrigger.points_awarded))
            .all()
        )

        notes = (
            db.query(InvestigationNote)
            .filter(InvestigationNote.alert_id == alert_id)
            .order_by(desc(InvestigationNote.created_at))
            .all()
        )

        return {
            "alert_id": alt.alert_id,
            "alert_ref": alt.alert_ref,
            "transaction_id": alt.transaction_id,
            "risk_score": alt.risk_score,
            "risk_category": alt.risk_category,
            "status": alt.status,
            "resolution_reason": alt.resolution_reason,
            "assigned_to": alt.assigned_to,
            "created_at": alt.created_at,
            "updated_at": alt.updated_at,
            "transaction_ref": txn.transaction_ref,
            "amount": txn.amount,
            "currency": txn.currency,
            "transaction_type": txn.transaction_type,
            "channel": txn.channel,
            "transaction_timestamp": txn.timestamp,
            "location_city": txn.location_city,
            "account_number": acct.account_number,
            "customer_ref": cust.customer_ref,
            "customer_name": f"{cust.first_name} {cust.last_name}",
            "triggers": triggers,
            "notes": notes
        }

    @staticmethod
    def update_alert_status(
        db: Session,
        alert_id: int,
        payload: AlertStatusUpdate
    ) -> Alert:
        """Update alert investigation state and optionally append status change note."""
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        old_status = alert.status
        alert.status = payload.status

        if payload.resolution_reason:
            alert.resolution_reason = payload.resolution_reason
        if payload.assigned_to:
            alert.assigned_to = payload.assigned_to

        alert.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # If note provided or status changed, record an automatic audit note
        note_text = payload.note
        if not note_text:
            note_text = f"Status changed from {old_status} to {payload.status}."
            if payload.resolution_reason:
                note_text += f" Resolution reason: {payload.resolution_reason}."

        audit_note = InvestigationNote(
            alert_id=alert_id,
            author=payload.assigned_to or "Risk Analyst",
            note_text=note_text,
            action_taken=f"Status update -> {payload.status}"
        )
        db.add(audit_note)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def add_investigation_note(
        db: Session,
        alert_id: int,
        payload: InvestigationNoteCreate
    ) -> InvestigationNote:
        """Add an analyst investigation note to the alert."""
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        note = InvestigationNote(
            alert_id=alert_id,
            author=payload.author,
            note_text=payload.note_text,
            action_taken=payload.action_taken
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return note
