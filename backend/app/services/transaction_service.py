import csv
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from backend.app.models.transaction import Transaction
from backend.app.models.account import Account
from backend.app.models.customer import Customer
from backend.app.models.alert import Alert
from backend.app.rules.engine import rule_engine
from backend.app.schemas.transaction import TransactionCreate

logger = logging.getLogger(__name__)

class TransactionService:

    @staticmethod
    def get_transactions(
        db: Session,
        page: int = 1,
        page_size: int = 25,
        account_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        channel: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        is_evaluated: Optional[bool] = None,
        risk_category: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc"
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Query transactions with comprehensive filtering, sorting, and pagination."""
        query = (
            db.query(
                Transaction,
                Account.account_number,
                Customer.first_name,
                Customer.last_name,
                Alert.risk_category,
                Alert.risk_score,
                Alert.alert_id
            )
            .join(Account, Transaction.account_id == Account.account_id)
            .join(Customer, Account.customer_id == Customer.customer_id)
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
        )

        if account_id:
            query = query.filter(Transaction.account_id == account_id)
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        if channel:
            query = query.filter(Transaction.channel == channel)
        if min_amount is not None:
            query = query.filter(Transaction.amount >= min_amount)
        if max_amount is not None:
            query = query.filter(Transaction.amount <= max_amount)
        if start_date:
            query = query.filter(Transaction.timestamp >= start_date)
        if end_date:
            query = query.filter(Transaction.timestamp <= end_date)
        if is_evaluated is not None:
            query = query.filter(Transaction.is_evaluated == is_evaluated)
        if risk_category:
            query = query.filter(Alert.risk_category == risk_category)
        if search:
            search_pat = f"%{search}%"
            query = query.filter(
                (Transaction.transaction_ref.like(search_pat)) |
                (Account.account_number.like(search_pat)) |
                (Customer.first_name.like(search_pat)) |
                (Customer.last_name.like(search_pat)) |
                (Transaction.location_city.like(search_pat))
            )

        total = query.count()

        # Sorting
        sort_column = getattr(Transaction, sort_by, Transaction.timestamp)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        items = []
        for row in results:
            txn = row[0]
            item = {
                "transaction_id": txn.transaction_id,
                "transaction_ref": txn.transaction_ref,
                "account_id": txn.account_id,
                "amount": txn.amount,
                "currency": txn.currency,
                "transaction_type": txn.transaction_type,
                "channel": txn.channel,
                "timestamp": txn.timestamp,
                "location_city": txn.location_city,
                "location_country": txn.location_country,
                "latitude": txn.latitude,
                "longitude": txn.longitude,
                "device_id": txn.device_id,
                "ip_address": txn.ip_address,
                "merchant_name": txn.merchant_name,
                "merchant_category": txn.merchant_category,
                "status": txn.status,
                "is_evaluated": txn.is_evaluated,
                "evaluated_at": txn.evaluated_at,
                "created_at": txn.created_at,
                "account_number": row[1],
                "customer_name": f"{row[2]} {row[3]}",
                "has_alert": row[6] is not None,
                "alert_risk_category": row[4],
                "alert_risk_score": row[5]
            }
            items.append(item)

        return total, items

    @staticmethod
    def get_transaction_by_id(db: Session, transaction_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve full details of a transaction including account, customer, and alert."""
        result = (
            db.query(
                Transaction,
                Account,
                Customer,
                Alert
            )
            .join(Account, Transaction.account_id == Account.account_id)
            .join(Customer, Account.customer_id == Customer.customer_id)
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
            .filter(Transaction.transaction_id == transaction_id)
            .first()
        )

        if not result:
            return None

        txn, acct, cust, alert = result
        return {
            "transaction": txn,
            "account": acct,
            "customer": cust,
            "alert": alert
        }

    @staticmethod
    def create_transaction(db: Session, payload: TransactionCreate) -> Transaction:
        """Create a single new transaction."""
        ref = payload.transaction_ref
        if not ref:
            now_str = payload.timestamp.strftime("%Y%m%d%H%M%S")
            ref = f"TXN-{now_str}-{payload.account_id}"

        txn = Transaction(
            transaction_ref=ref,
            account_id=payload.account_id,
            amount=payload.amount,
            currency=payload.currency,
            transaction_type=payload.transaction_type,
            channel=payload.channel,
            timestamp=payload.timestamp,
            location_city=payload.location_city,
            location_country=payload.location_country,
            latitude=payload.latitude,
            longitude=payload.longitude,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
            merchant_name=payload.merchant_name,
            merchant_category=payload.merchant_category,
            status=payload.status,
            is_evaluated=False
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return txn

    @staticmethod
    def import_transactions_from_csv(db: Session, csv_content: str) -> Dict[str, Any]:
        """
        Parses CSV data, validates fields, and records valid transactions.
        Reports parsed, imported, skipped, and specific row-level errors.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        imported_count = 0
        errors = []

        required_cols = {"account_id", "amount", "transaction_type", "timestamp", "location_city"}
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            missing = required_cols - set(reader.fieldnames or [])
            return {
                "success": False,
                "error": f"CSV is missing required header columns: {', '.join(missing)}",
                "imported_count": 0,
                "errors": []
            }

        # Cache existing account IDs and account numbers for foreign key mapping
        all_accounts = db.query(Account).all()
        existing_account_ids = {a.account_id for a in all_accounts}
        acc_num_map = {a.account_number.strip().upper(): a.account_id for a in all_accounts}

        # Cache synthetic customer to auto-link unknown accounts if needed
        default_customer = db.query(Customer).first()

        for row_idx, row in enumerate(reader, start=2):
            try:
                raw_acct = str(row.get("account_id", "")).strip()
                if not raw_acct:
                    errors.append({"row": row_idx, "error": "Account identifier is missing or empty."})
                    continue

                acct_id = None
                # Check if it's already an integer ID
                if raw_acct.isdigit():
                    cand_id = int(raw_acct)
                    if cand_id in existing_account_ids:
                        acct_id = cand_id

                # If not matched by ID, check if it matches an existing account_number
                if acct_id is None:
                    acct_id = acc_num_map.get(raw_acct.upper())

                # If still not found, auto-create the Account in the DB so foreign key constraints pass
                if acct_id is None:
                    new_acc = Account(
                        account_number=raw_acct,
                        customer_id=default_customer.customer_id if default_customer else 1,
                        account_type="CHECKING",
                        currency=row.get("currency", "USD").strip().upper() or "USD",
                        current_balance=Decimal("25000.00"),
                        status="ACTIVE"
                    )
                    db.add(new_acc)
                    db.flush()  # populate new_acc.account_id
                    acct_id = new_acc.account_id
                    existing_account_ids.add(acct_id)
                    acc_num_map[raw_acct.upper()] = acct_id

                amount_val = Decimal(row.get("amount", "").strip())
                if amount_val <= Decimal('0'):
                    errors.append({"row": row_idx, "error": f"Amount must be greater than zero. Got {amount_val}."})
                    continue

                # Parse timestamp
                ts_str = row.get("timestamp", "").strip()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

                txn_ref = row.get("transaction_ref", "").strip()
                if not txn_ref:
                    txn_ref = f"CSV-{ts.strftime('%Y%m%d%H%M%S')}-{row_idx}"

                # Check unique ref
                existing = db.query(Transaction).filter(Transaction.transaction_ref == txn_ref).first()
                if existing:
                    errors.append({"row": row_idx, "error": f"Transaction reference '{txn_ref}' already exists."})
                    continue

                lat_str = row.get("latitude", "").strip()
                lon_str = row.get("longitude", "").strip()

                raw_type = row.get("transaction_type", "TRANSFER").strip().upper()
                # Normalize common aliases (e.g. DEBIT -> WITHDRAWAL, CREDIT -> DEPOSIT)
                if raw_type == "DEBIT":
                    tx_type = "WITHDRAWAL"
                elif raw_type == "CREDIT":
                    tx_type = "DEPOSIT"
                else:
                    tx_type = raw_type

                txn = Transaction(
                    transaction_ref=txn_ref,
                    account_id=acct_id,
                    amount=amount_val,
                    currency=row.get("currency", "USD").strip().upper() or "USD",
                    transaction_type=tx_type,
                    channel=row.get("channel", "ONLINE").strip().upper() or "ONLINE",
                    timestamp=ts,
                    location_city=row.get("location_city", "Unknown").strip(),
                    location_country=row.get("location_country", "India").strip(),
                    latitude=Decimal(lat_str) if lat_str else None,
                    longitude=Decimal(lon_str) if lon_str else None,
                    device_id=row.get("device_id", "").strip() or None,
                    ip_address=row.get("ip_address", "").strip() or None,
                    merchant_name=row.get("merchant_name", "").strip() or None,
                    merchant_category=row.get("merchant_category", "").strip() or None,
                    status=row.get("status", "COMPLETED").strip().upper(),
                    is_evaluated=False
                )
                db.add(txn)
                imported_count += 1
            except Exception as e:
                errors.append({"row": row_idx, "error": str(e)})

        db.commit()
        return {
            "success": True,
            "imported_count": imported_count,
            "error_count": len(errors),
            "errors": errors[:50]  # Cap error list
        }

    @staticmethod
    def evaluate_transaction(
        db: Session,
        transaction_id: int,
        force_reevaluate: bool = False
    ) -> Dict[str, Any]:
        """Evaluates a single transaction via the Rule Engine."""
        txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
        if not txn:
            raise ValueError(f"Transaction with ID {transaction_id} not found.")

        score, category, results, alert = rule_engine.evaluate_transaction(
            transaction=txn,
            db=db,
            force_reevaluate=force_reevaluate
        )

        triggered = [r for r in results if r.triggered]

        return {
            "transaction_id": txn.transaction_id,
            "transaction_ref": txn.transaction_ref,
            "is_flagged": len(triggered) > 0,
            "risk_score": score,
            "risk_category": category,
            "alert_ref": alert.alert_ref if alert else None,
            "triggers_count": len(triggered),
            "triggered_rules": [
                {
                    "rule_code": r.rule_code,
                    "rule_name": r.rule_name,
                    "points": r.points,
                    "reason": r.reason,
                    "context": r.context
                }
                for r in triggered
            ],
            "all_rule_results": [
                {
                    "rule_code": r.rule_code,
                    "rule_name": r.rule_name,
                    "triggered": r.triggered,
                    "points": r.points,
                    "reason": r.reason,
                    "parameters_used": r.parameters_used,
                    "insufficient_data": r.insufficient_data
                }
                for r in results
            ]
        }

    @staticmethod
    def batch_evaluate(
        db: Session,
        only_unevaluated: bool = True,
        limit: int = 500
    ) -> Dict[str, Any]:
        """Runs the rule engine over a batch of eligible transactions."""
        query = db.query(Transaction)
        if only_unevaluated:
            query = query.filter(Transaction.is_evaluated == False)
        
        query = query.order_by(Transaction.timestamp.asc()).limit(limit)
        txns = query.all()

        evaluated_count = 0
        flagged_count = 0
        alerts_created = 0
        cat_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

        for txn in txns:
            score, category, results, alert = rule_engine.evaluate_transaction(
                transaction=txn,
                db=db,
                force_reevaluate=not only_unevaluated
            )
            evaluated_count += 1
            cat_counts[category] = cat_counts.get(category, 0) + 1
            if alert:
                flagged_count += 1
                alerts_created += 1

        return {
            "evaluated_count": evaluated_count,
            "flagged_count": flagged_count,
            "alerts_created": alerts_created,
            "critical_count": cat_counts.get("CRITICAL", 0),
            "high_count": cat_counts.get("HIGH", 0),
            "medium_count": cat_counts.get("MEDIUM", 0),
            "low_count": cat_counts.get("LOW", 0),
            "message": f"Successfully evaluated {evaluated_count} transactions. Flagged {flagged_count} suspicious items."
        }
