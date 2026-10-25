from typing import Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from backend.app.models.transaction import Transaction
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult

class HighValueTransactionRule(BaseFraudRule):
    """
    Rule A: High-Value Transaction Rule
    Flags single transactions exceeding a configurable monetary threshold.
    Default threshold: $10,000.00 USD.
    """
    def __init__(self):
        super().__init__(
            rule_code="RULE_HIGH_VALUE",
            rule_name="High-Value Transaction Threshold",
            default_points=35
        )

    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        params = parameters or {}
        threshold = Decimal(str(params.get("threshold", 10000.00)))
        currency = str(params.get("currency", "USD"))
        points = configured_points if configured_points is not None else self.default_points

        if transaction.amount is None:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason="Transaction amount is missing or invalid.",
                parameters_used={"threshold": float(threshold), "currency": currency},
                context={"error": "missing_amount"}
            )

        tx_amount = Decimal(str(transaction.amount))
        is_triggered = tx_amount >= threshold

        if is_triggered:
            reason = (
                f"Transaction amount of {tx_amount:,.2f} {transaction.currency or currency} "
                f"meets or exceeds the configured threshold of {threshold:,.2f} {currency}."
            )
            awarded = points
        else:
            reason = (
                f"Transaction amount of {tx_amount:,.2f} {transaction.currency or currency} "
                f"is within the permissible limit (< {threshold:,.2f} {currency})."
            )
            awarded = 0

        return RuleEvaluationResult(
            rule_code=self.rule_code,
            rule_name=self.rule_name,
            triggered=is_triggered,
            points=awarded,
            reason=reason,
            parameters_used={"threshold": float(threshold), "currency": currency},
            context={
                "transaction_amount": float(tx_amount),
                "threshold": float(threshold),
                "excess_amount": float(max(Decimal('0'), tx_amount - threshold))
            }
        )
