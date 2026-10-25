from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import timedelta
import statistics
from sqlalchemy.orm import Session
from backend.app.models.transaction import Transaction
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult

class UnusualSpendingRule(BaseFraudRule):
    """
    Rule E: Unusual Spending vs Historical Baseline Rule
    Compares the transaction amount against the customer's prior spending baseline.
    Requires a minimum number of prior completed transactions (default: 5).
    If insufficient history exists (< 5 transactions), returns an insufficient-history result
    instead of fabricating a synthetic baseline.
    Flags transactions where amount > baseline_multiplier * historical_mean (default multiplier: 3.0x).
    """
    def __init__(self):
        super().__init__(
            rule_code="RULE_UNUSUAL_SPENDING",
            rule_name="Deviant Spending vs Historical Baseline",
            default_points=25
        )

    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        params = parameters or {}
        multiplier = float(params.get("baseline_multiplier", 3.0))
        min_history = int(params.get("min_historical_txns", 5))
        lookback_days = int(params.get("lookback_days", 30))
        points = configured_points if configured_points is not None else self.default_points

        parameters_used = {
            "baseline_multiplier": multiplier,
            "min_historical_txns": min_history,
            "lookback_days": lookback_days
        }

        if transaction.amount is None or not transaction.timestamp or not transaction.account_id:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason="Required transaction fields (amount, timestamp, account) are missing.",
                parameters_used=parameters_used,
                context={"error": "missing_required_fields"}
            )

        current_amount = float(transaction.amount)
        lookback_start = transaction.timestamp - timedelta(days=lookback_days)

        # Retrieve prior completed transactions for the same account
        prior_txs = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == transaction.account_id,
                Transaction.timestamp < transaction.timestamp,
                Transaction.timestamp >= lookback_start,
                Transaction.status == "COMPLETED",
                Transaction.transaction_id != transaction.transaction_id
            )
            .all()
        )

        prior_count = len(prior_txs)

        # Explicit check for insufficient history
        if prior_count < min_history:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason=(
                    f"Insufficient historical data to establish a reliable spending baseline. "
                    f"Found {prior_count} prior completed transactions (minimum required: {min_history} within {lookback_days} days)."
                ),
                parameters_used=parameters_used,
                context={
                    "historical_records_found": prior_count,
                    "min_required_records": min_history,
                    "lookback_days": lookback_days
                },
                insufficient_data=True
            )

        # Calculate statistical baseline
        prior_amounts = [float(t.amount) for t in prior_txs]
        mean_amount = statistics.mean(prior_amounts)
        stdev_amount = statistics.stdev(prior_amounts) if prior_count > 1 else 0.0
        threshold_amount = round(mean_amount * multiplier, 2)

        is_triggered = current_amount > threshold_amount

        context = {
            "historical_count": prior_count,
            "historical_mean": round(mean_amount, 2),
            "historical_stdev": round(stdev_amount, 2),
            "baseline_multiplier": multiplier,
            "spending_threshold": threshold_amount,
            "current_amount": current_amount,
            "deviation_ratio": round(current_amount / mean_amount, 2) if mean_amount > 0 else 0
        }

        if is_triggered:
            reason = (
                f"Transaction amount of ${current_amount:,.2f} significantly deviates from "
                f"historical 30-day baseline average (${mean_amount:,.2f}), exceeding {multiplier}x the mean "
                f"(threshold: ${threshold_amount:,.2f}, ratio: {round(current_amount / mean_amount, 1)}x)."
            )
            awarded = points
        else:
            reason = (
                f"Transaction amount of ${current_amount:,.2f} is consistent with "
                f"account historical baseline (mean: ${mean_amount:,.2f}, threshold: ${threshold_amount:,.2f})."
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
