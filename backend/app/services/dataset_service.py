import csv
import io
import os
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.dataset import Dataset
from backend.app.models.transaction import Transaction
from backend.app.models.account import Account
from backend.app.models.customer import Customer
from backend.app.models.alert import Alert
from backend.app.rules.engine import rule_engine

logger = logging.getLogger(__name__)

# Temporary in-memory cache for CSV uploads during preview before confirmation
# Structure: { token: { "filename": str, "file_size": int, "content": str, "created_at": datetime } }
PREVIEW_CACHE: Dict[str, Dict[str, Any]] = {}

# Required semantic fields
REQUIRED_FIELDS = ["account_id", "amount", "transaction_type", "timestamp", "location_city"]

# Synonym mapping helper
SYNONYMS = {
    "account_id": ["account_id", "account", "account_number", "account_no", "acct_id", "acct_no", "acc_id", "acc_no"],
    "amount": ["amount", "txn_amount", "transaction_amount", "amt", "value"],
    "transaction_type": ["transaction_type", "type", "txn_type", "trans_type", "action"],
    "timestamp": ["timestamp", "date", "datetime", "txn_time", "transaction_time", "time"],
    "location_city": ["location_city", "city", "location", "place", "city_name"],
    "customer_id": ["customer_id", "cust_id", "client_id", "user_id", "customer_number"],
    "customer_name": ["customer_name", "name", "client_name", "full_name", "customer"],
    "email": ["email", "email_address", "contact_email", "mail"],
    "customer_email": ["customer_email", "customer_mail"],
    "customer_category": ["customer_category", "customer_type", "client_category", "client_type", "cust_category"],
    "account_balance": ["account_balance", "balance", "current_balance", "acct_balance"],
    "currency": ["currency", "curr", "curr_code"],
    "channel": ["channel", "channel_type", "medium"],
    "transaction_ref": ["transaction_ref", "ref", "reference", "txn_ref", "transaction_id", "tx_id"],
    "location_country": ["location_country", "country"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng"],
    "device_id": ["device_id", "device"],
    "ip_address": ["ip_address", "ip"],
    "merchant_name": ["merchant_name", "merchant", "description"],
    "merchant_category": ["merchant_category", "category", "mcc"]
}

class DatasetService:

    @staticmethod
    def get_active_dataset(db: Session) -> Optional[Dataset]:
        """Returns the currently active dataset."""
        return db.query(Dataset).filter(Dataset.is_active == True).first()

    @staticmethod
    def get_all_datasets(db: Session) -> List[Dataset]:
        """Returns list of all datasets ordered by creation time descending."""
        return db.query(Dataset).order_by(Dataset.created_at.desc()).all()

    @staticmethod
    def set_active_dataset(db: Session, dataset_id: int) -> Optional[Dataset]:
        """Switches the active dataset without deleting any data."""
        target = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        if not target:
            return None
        # Deactivate all others
        db.query(Dataset).update({Dataset.is_active: False})
        target.is_active = True
        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def preview_csv(file_content_str: str, filename: str, file_size: int) -> Dict[str, Any]:
        """
        Parses CSV, performs validation checks, generates first 10-20 sample preview rows,
        and creates a temporary token for subsequent confirmation.
        """
        token = str(uuid.uuid4())
        PREVIEW_CACHE[token] = {
            "filename": filename,
            "file_size": file_size,
            "content": file_content_str,
            "created_at": datetime.now(timezone.utc)
        }

        # Clean preview cache older than 1 hour
        now = datetime.now(timezone.utc)
        to_del = [t for t, d in PREVIEW_CACHE.items() if (now - d["created_at"]).total_seconds() > 3600]
        for t in to_del:
            PREVIEW_CACHE.pop(t, None)

        reader = csv.DictReader(io.StringIO(file_content_str))
        raw_headers = [h.strip() for h in (reader.fieldnames or []) if h]

        # Detect column mappings
        header_lower_map = {h.lower().replace(" ", "_"): h for h in raw_headers}
        detected_mappings = {}
        missing_required = []

        for req in REQUIRED_FIELDS:
            matched = False
            for syn in SYNONYMS.get(req, [req]):
                if syn in header_lower_map:
                    detected_mappings[req] = header_lower_map[syn]
                    matched = True
                    break
            if not matched:
                missing_required.append(req)

        # Also detect optional field mappings for the UI mapping panel
        OPTIONAL_FIELDS = [
            "customer_id", "customer_name", "email", "customer_email", "customer_category",
            "account_balance", "currency", "channel", "transaction_ref", "location_country",
            "latitude", "longitude", "device_id", "ip_address", "merchant_name", "merchant_category"
        ]
        for opt in OPTIONAL_FIELDS:
            if opt not in detected_mappings:
                for syn in SYNONYMS.get(opt, [opt]):
                    if syn in header_lower_map:
                        detected_mappings[opt] = header_lower_map[syn]
                        break

        # Inspect rows for validation metrics
        total_rows = 0
        preview_rows = []
        invalid_amounts = 0
        invalid_timestamps = 0
        duplicate_refs = 0
        seen_refs = set()

        for idx, row in enumerate(reader):
            total_rows += 1
            if len(preview_rows) < 20:
                preview_rows.append({k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k})

            # Check amount if mapped
            amt_col = detected_mappings.get("amount")
            if amt_col and amt_col in row:
                try:
                    val = Decimal(str(row[amt_col]).strip())
                    if val <= 0:
                        invalid_amounts += 1
                except Exception:
                    invalid_amounts += 1

            # Check timestamp if mapped
            ts_col = detected_mappings.get("timestamp")
            if ts_col and ts_col in row:
                ts_str = str(row[ts_col]).strip()
                try:
                    datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    try:
                        datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        invalid_timestamps += 1

            # Check ref if present
            ref_col = detected_mappings.get("transaction_ref") or detected_mappings.get("account_id")
            if ref_col and ref_col in row:
                raw_ref = str(row[ref_col]).strip()
                if raw_ref:
                    if raw_ref in seen_refs:
                        duplicate_refs += 1
                    else:
                        seen_refs.add(raw_ref)

        validation_passed = len(missing_required) == 0 and total_rows > 0
        summary_parts = []
        if total_rows == 0:
            summary_parts.append("CSV file contains no transaction rows.")
        elif len(missing_required) > 0:
            summary_parts.append(f"Missing required columns: {', '.join(missing_required)}.")
        else:
            summary_parts.append(f"Valid schema detected with {total_rows:,} records.")

        if invalid_amounts > 0:
            summary_parts.append(f"Found {invalid_amounts} rows with non-positive or malformed amounts.")
        if invalid_timestamps > 0:
            summary_parts.append(f"Found {invalid_timestamps} rows with unrecognized timestamp formats.")
        if duplicate_refs > 0:
            summary_parts.append(f"Found {duplicate_refs} duplicate references.")

        return {
            "filename": filename,
            "file_size_bytes": file_size,
            "total_rows": total_rows,
            "total_columns": len(raw_headers),
            "columns": raw_headers,
            "preview_rows": preview_rows,
            "missing_required_columns": missing_required,
            "detected_mappings": detected_mappings,
            "invalid_amounts_count": invalid_amounts,
            "invalid_timestamps_count": invalid_timestamps,
            "duplicate_refs_count": duplicate_refs,
            "validation_passed": validation_passed,
            "validation_summary": " ".join(summary_parts),
            "temp_file_token": token
        }

    @staticmethod
    def confirm_and_import(
        db: Session,
        temp_file_token: str,
        filename: str,
        file_size: Optional[int] = None,
        file_size_bytes: Optional[int] = None,
        custom_mapping: Optional[Dict[str, str]] = None
    ) -> Dataset:
        """
        Creates a new Dataset record, marks it active, parses the cached CSV content,
        and saves all transactions linked to this dataset_id.
        """
        cached = PREVIEW_CACHE.get(temp_file_token)
        if not cached:
            raise ValueError("CSV upload session expired or invalid. Please re-upload the file.")

        resolved_file_size = file_size_bytes if file_size_bytes is not None else (file_size if file_size is not None else cached.get("file_size", 0))

        content_str = cached["content"]
        reader = csv.DictReader(io.StringIO(content_str))
        raw_headers = [h.strip() for h in (reader.fieldnames or []) if h]
        header_lower_map = {h.lower().replace(" ", "_"): h for h in raw_headers}

        # Resolve mappings
        col_map = {}
        for req in REQUIRED_FIELDS:
            if custom_mapping and custom_mapping.get(req):
                col_map[req] = custom_mapping[req]
            else:
                for syn in SYNONYMS.get(req, [req]):
                    if syn in header_lower_map:
                        col_map[req] = header_lower_map[syn]
                        break

        # Check optional mappings
        optional_fields = [
            "customer_id", "customer_name", "email", "customer_email", "customer_category",
            "account_balance", "currency", "channel", "transaction_ref", "location_country",
            "latitude", "longitude", "device_id", "ip_address",
            "merchant_name", "merchant_category"
        ]
        for opt in optional_fields:
            if custom_mapping and custom_mapping.get(opt):
                col_map[opt] = custom_mapping[opt]
            else:
                for syn in SYNONYMS.get(opt, [opt]):
                    if syn in header_lower_map:
                        col_map[opt] = header_lower_map[syn]
                        break

        # Deactivate existing datasets
        db.query(Dataset).update({Dataset.is_active: False})

        # Create new dataset in UPLOADED status
        dataset = Dataset(
            filename=filename or cached.get("filename", "transactions.csv"),
            file_size_bytes=resolved_file_size,
            total_rows=0,
            total_columns=len(raw_headers),
            is_active=True,
            status="UPLOADED",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(dataset)
        db.flush()

        # Cache dataset-scoped customers and accounts
        dataset_customers: Dict[str, Customer] = {}
        dataset_accounts: Dict[str, Account] = {}

        row_count = 0
        for row_idx, row in enumerate(reader, start=2):
            try:
                acct_col = col_map.get("account_id")
                raw_acct = str(row.get(acct_col, "")).strip() if acct_col else f"ACC-{row_idx}"
                if not raw_acct:
                    raw_acct = f"ACC-{row_idx}"

                # Extract optional customer fields
                cust_id_col = col_map.get("customer_id")
                raw_cust_id = str(row.get(cust_id_col, "")).strip() if cust_id_col and row.get(cust_id_col) is not None else None
                if raw_cust_id in ("", "None", "null", "undefined"):
                    raw_cust_id = None

                cust_name_col = col_map.get("customer_name")
                raw_cust_name = str(row.get(cust_name_col, "")).strip() if cust_name_col and row.get(cust_name_col) is not None else None
                if raw_cust_name in ("", "None", "null", "undefined"):
                    raw_cust_name = None

                email_col = col_map.get("email") or col_map.get("customer_email")
                raw_email = str(row.get(email_col, "")).strip() if email_col and row.get(email_col) is not None else None
                if raw_email in ("", "None", "null", "undefined"):
                    raw_email = None

                cat_col = col_map.get("customer_category")
                raw_customer_cat = str(row.get(cat_col, "")).strip() if cat_col and row.get(cat_col) is not None else None
                if raw_customer_cat in ("", "None", "null", "undefined"):
                    raw_customer_cat = None

                bal_col = col_map.get("account_balance")
                raw_balance = None
                if bal_col and row.get(bal_col) is not None:
                    bal_str = str(row.get(bal_col, "")).strip()
                    if bal_str:
                        try:
                            raw_balance = Decimal(bal_str)
                        except Exception:
                            raw_balance = None

                curr_col = col_map.get("currency")
                raw_curr = str(row.get(curr_col, "USD")).strip().upper() if curr_col and row.get(curr_col) else "USD"

                # Customer entity handling (ONLY when customer_id is provided)
                linked_cust_id = None
                if raw_cust_id:
                    if raw_cust_id not in dataset_customers:
                        new_cust = Customer(
                            customer_ref=raw_cust_id,
                            first_name=raw_cust_name or "Not provided",
                            last_name="",
                            email=raw_email or "Not provided",
                            dataset_id=dataset.dataset_id,
                            risk_segment="STANDARD",
                            account_status="ACTIVE"
                        )
                        db.add(new_cust)
                        db.flush()
                        dataset_customers[raw_cust_id] = new_cust
                    else:
                        existing_cust = dataset_customers[raw_cust_id]
                        if raw_cust_name and (existing_cust.first_name == "Not provided" or not existing_cust.first_name):
                            existing_cust.first_name = raw_cust_name
                        if raw_email and (existing_cust.email == "Not provided" or not existing_cust.email):
                            existing_cust.email = raw_email

                    linked_cust_id = dataset_customers[raw_cust_id].customer_id

                # Account entity handling (scoped to dataset)
                acct_key = raw_acct.upper()
                if acct_key not in dataset_accounts:
                    new_acc = Account(
                        account_number=raw_acct,
                        customer_id=linked_cust_id,
                        dataset_id=dataset.dataset_id,
                        customer_name=raw_cust_name,
                        email=raw_email,
                        customer_ref=raw_cust_id,
                        customer_category=raw_customer_cat,
                        account_type="CHECKING",
                        currency=raw_curr,
                        current_balance=raw_balance,
                        status="ACTIVE"
                    )
                    db.add(new_acc)
                    db.flush()
                    dataset_accounts[acct_key] = new_acc
                else:
                    existing_acc = dataset_accounts[acct_key]
                    if linked_cust_id and not existing_acc.customer_id:
                        existing_acc.customer_id = linked_cust_id
                    if raw_cust_name and not existing_acc.customer_name:
                        existing_acc.customer_name = raw_cust_name
                    if raw_email and not existing_acc.email:
                        existing_acc.email = raw_email
                    if raw_cust_id and not existing_acc.customer_ref:
                        existing_acc.customer_ref = raw_cust_id
                    if raw_customer_cat and not existing_acc.customer_category:
                        existing_acc.customer_category = raw_customer_cat
                    if raw_balance is not None and existing_acc.current_balance is None:
                        existing_acc.current_balance = raw_balance

                acct_id = dataset_accounts[acct_key].account_id

                # Amount
                amt_col = col_map.get("amount")
                amt_str = str(row.get(amt_col, "100.00")).strip()
                try:
                    amount_val = Decimal(amt_str)
                    if amount_val <= 0:
                        amount_val = Decimal("10.00")
                except Exception:
                    amount_val = Decimal("10.00")

                # Timestamp
                ts_col = col_map.get("timestamp")
                ts_str = str(row.get(ts_col, "")).strip()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        ts = datetime.now(timezone.utc).replace(tzinfo=None)

                # Reference
                ref_col = col_map.get("transaction_ref")
                txn_ref = str(row.get(ref_col, "")).strip() if ref_col else None
                if not txn_ref:
                    txn_ref = f"DS{dataset.dataset_id}-{ts.strftime('%Y%m%d%H%M%S')}-{row_idx}"

                # Ensure uniqueness
                existing_txn = db.query(Transaction).filter(Transaction.transaction_ref == txn_ref).first()
                if existing_txn:
                    txn_ref = f"{txn_ref}-D{dataset.dataset_id}-{uuid.uuid4().hex[:6]}"

                # Transaction Type
                type_col = col_map.get("transaction_type")
                raw_type = str(row.get(type_col, "TRANSFER")).strip().upper() if type_col else "TRANSFER"
                if raw_type == "DEBIT":
                    tx_type = "WITHDRAWAL"
                elif raw_type == "CREDIT":
                    tx_type = "DEPOSIT"
                else:
                    tx_type = raw_type

                # City & Country
                city_col = col_map.get("location_city")
                city = str(row.get(city_col, "Unknown")).strip() if city_col else "Unknown"

                country_col = col_map.get("location_country")
                country = str(row.get(country_col, "USA")).strip() if country_col else "USA"

                # Lat / Lon
                lat_col = col_map.get("latitude")
                lon_col = col_map.get("longitude")
                lat_str = str(row.get(lat_col, "")).strip() if lat_col else ""
                lon_str = str(row.get(lon_col, "")).strip() if lon_col else ""

                chan_col = col_map.get("channel")
                raw_channel = str(row.get(chan_col, "ONLINE")).strip().upper() if chan_col and row.get(chan_col) else "ONLINE"

                merch_name_col = col_map.get("merchant_name")
                raw_merch_name = str(row.get(merch_name_col, "")).strip() if merch_name_col and row.get(merch_name_col) else None
                if raw_merch_name in ("", "None", "null"):
                    raw_merch_name = None

                merch_cat_col = col_map.get("merchant_category")
                raw_merch_cat = str(row.get(merch_cat_col, "")).strip() if merch_cat_col and row.get(merch_cat_col) else None
                if raw_merch_cat in ("", "None", "null"):
                    raw_merch_cat = None

                txn = Transaction(
                    dataset_id=dataset.dataset_id,
                    transaction_ref=txn_ref,
                    account_id=acct_id,
                    account_ref=raw_acct,
                    customer_ref=raw_cust_id,
                    customer_name=raw_cust_name,
                    email=raw_email,
                    customer_category=raw_customer_cat,
                    account_balance=raw_balance,
                    amount=amount_val,
                    currency=raw_curr,
                    transaction_type=tx_type,
                    channel=raw_channel,
                    timestamp=ts,
                    location_city=city,
                    location_country=country,
                    latitude=Decimal(lat_str) if lat_str else None,
                    longitude=Decimal(lon_str) if lon_str else None,
                    device_id=None,
                    ip_address=None,
                    merchant_name=raw_merch_name,
                    merchant_category=raw_merch_cat,
                    status="COMPLETED",
                    is_evaluated=False
                )
                db.add(txn)
                row_count += 1
            except Exception as e:
                logger.warning(f"Error parsing row {row_idx}: {e}")

        dataset.total_rows = row_count
        db.commit()
        db.refresh(dataset)

        # Clear preview cache
        PREVIEW_CACHE.pop(temp_file_token, None)
        return dataset

    @staticmethod
    def run_analysis(db: Session, dataset_id: int) -> Dict[str, Any]:
        """
        Executes the 5 detection rules on all unevaluated transactions for the specified dataset.
        Generates alerts, sets status to ANALYSED, and returns complete summary.
        """
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found.")

        txns = db.query(Transaction).filter(
            Transaction.dataset_id == dataset_id,
            Transaction.is_evaluated == False
        ).order_by(Transaction.timestamp.asc()).all()

        res = rule_engine.evaluate_batch(db=db, transactions=txns, force_reevaluate=False)
        flagged_count = res["flagged_count"]

        dataset.status = "ANALYSED"
        dataset.analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(dataset)

        # Totals for this dataset
        total_in_ds = db.query(func.count(Transaction.transaction_id)).filter(Transaction.dataset_id == dataset_id).scalar() or 0
        total_eval = db.query(func.count(Transaction.transaction_id)).filter(Transaction.dataset_id == dataset_id, Transaction.is_evaluated == True).scalar() or 0
        open_alerts_cnt = (
            db.query(func.count(Alert.alert_id))
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .filter(Transaction.dataset_id == dataset_id, Alert.status == "OPEN")
            .scalar() or 0
        )
        high_crit_cnt = (
            db.query(func.count(Alert.alert_id))
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            .filter(Transaction.dataset_id == dataset_id, Alert.risk_category.in_(["HIGH", "CRITICAL"]))
            .scalar() or 0
        )

        return {
            "dataset_id": dataset.dataset_id,
            "status": dataset.status,
            "total_transactions": total_in_ds,
            "evaluated_transactions": total_eval,
            "clean_transactions": total_eval - flagged_count,
            "flagged_transactions": flagged_count,
            "open_alerts": open_alerts_cnt,
            "high_critical_alerts": high_crit_cnt,
            "is_complete": True,
            "message": f"Successfully analysed {total_eval:,} transactions. Identified {flagged_count:,} risk indicators."
        }
