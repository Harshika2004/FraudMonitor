from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.transaction import Transaction
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult

class UnusualTransactionTimingRule(BaseFraudRule):
    """
    Rule C: Unusual Transaction Timing Rule
    Identifies transactions processed during atypical off-hours.
    Default assumption: Transactions occurring between 01:00 AM and 05:00 AM local time
    exhibit higher statistical probability of unauthorized or bot-driven operations.
    """
    def __init__(self):
        super().__init__(
            rule_code="RULE_UNUSUAL_TIMING",
            rule_name="Unusual Transaction Timing",
            default_points=20
        )

    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        params = parameters or {}
        start_hour = int(params.get("start_hour", 1))   # 01:00 AM (inclusive)
        end_hour = int(params.get("end_hour", 5))       # 05:00 AM (inclusive)
        points = configured_points if configured_points is not None else self.default_points

        if not transaction.timestamp:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason="Transaction timestamp is missing.",
                parameters_used={"start_hour": start_hour, "end_hour": end_hour},
                context={"error": "missing_timestamp"}
            )

        tx_hour = transaction.timestamp.hour

        # Check if transaction hour falls within the off-hours window
        # Supports standard range [start_hour, end_hour] (e.g. 1 to 5) or wrapped overnight (e.g. 23 to 4)
        if start_hour <= end_hour:
            is_triggered = (start_hour <= tx_hour <= end_hour)
        else:
            is_triggered = (tx_hour >= start_hour or tx_hour <= end_hour)

        parameters_used = {
            "start_hour": start_hour,
            "end_hour": end_hour,
            "time_window_description": f"{start_hour:02d}:00 to {end_hour:02d}:59"
        }

        context = {
            "transaction_timestamp": transaction.timestamp.isoformat(),
            "transaction_hour": tx_hour,
            "off_hours_window": f"{start_hour:02d}:00 - {end_hour:02d}:59"
        }

        if is_triggered:
            reason = (
                f"Transaction executed at {transaction.timestamp.strftime('%H:%M:%S')} "
                f"(hour {tx_hour}), which falls within the flagged off-hours window ({start_hour:02d}:00 - {end_hour:02d}:59)."
            )
            awarded = points
        else:
            reason = (
                f"Transaction timestamp {transaction.timestamp.strftime('%H:%M:%S')} "
                f"is within typical operating hours."
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
