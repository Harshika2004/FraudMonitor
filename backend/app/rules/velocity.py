from typing import Dict, Any, Optional
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.transaction import Transaction
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult

class TransactionVelocityRule(BaseFraudRule):
    """
    Rule B: Transaction Velocity Rule
    Detects rapid repeated transactions on the same account within a configurable time window.
    Default: >= 3 transactions within 60 minutes.
    """
    def __init__(self):
        super().__init__(
            rule_code="RULE_VELOCITY",
            rule_name="High Transaction Velocity",
            default_points=30
        )

    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        params = parameters or {}
        time_window_minutes = int(params.get("time_window_minutes", 60))
        count_threshold = int(params.get("transaction_count_threshold", 3))
        points = configured_points if configured_points is not None else self.default_points

        if not transaction.timestamp or not transaction.account_id:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason="Transaction timestamp or account ID missing.",
                parameters_used={"time_window_minutes": time_window_minutes, "transaction_count_threshold": count_threshold},
                context={"error": "missing_required_fields"}
            )

        window_start = transaction.timestamp - timedelta(minutes=time_window_minutes)

        # Count transactions in this account within [window_start, transaction.timestamp]
        # Include current transaction in the window count
        recent_txs = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == transaction.account_id,
                Transaction.timestamp >= window_start,
                Transaction.timestamp <= transaction.timestamp
            )
            .order_by(Transaction.timestamp.desc())
            .all()
        )

        txn_count = len(recent_txs)
        is_triggered = txn_count >= count_threshold

        parameters_used = {
            "time_window_minutes": time_window_minutes,
            "transaction_count_threshold": count_threshold
        }

        context = {
            "account_id": transaction.account_id,
            "window_start": window_start.isoformat(),
            "window_end": transaction.timestamp.isoformat(),
            "transaction_count_in_window": txn_count,
            "threshold": count_threshold,
            "recent_transaction_ids": [t.transaction_id for t in recent_txs[:10]]
        }

        if is_triggered:
            reason = (
                f"Observed {txn_count} transactions on account {transaction.account_id} "
                f"within {time_window_minutes} minutes, reaching or exceeding the threshold of {count_threshold}."
            )
            awarded = points
        else:
            reason = (
                f"Transaction count ({txn_count}) within the {time_window_minutes}-minute "
                f"lookback is below the velocity threshold of {count_threshold}."
            )
            awarded = 0

        return RuleEvaluationResult(
            rule_code=self.rule_code,
            rule_name=self.rule_name,
            triggered=is_triggered,
            points=awarded,
            reason=reason,
            parameters_used=parameters_used,
            context=context
        )
