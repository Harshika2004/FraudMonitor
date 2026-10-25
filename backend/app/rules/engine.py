import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.transaction import Transaction
from backend.app.models.rule import FraudRule
from backend.app.models.alert import Alert, AlertRuleTrigger
from backend.app.models.risk_config import RiskScoreConfiguration
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult
from backend.app.rules.high_value import HighValueTransactionRule
from backend.app.rules.velocity import TransactionVelocityRule
from backend.app.rules.unusual_timing import UnusualTransactionTimingRule
from backend.app.rules.geographic_anomaly import GeographicAnomalyRule
from backend.app.rules.unusual_spending import UnusualSpendingRule

logger = logging.getLogger(__name__)

class FraudDetectionEngine:
    """
    Deterministic, explainable fraud rule evaluation engine.
    Orchestrates execution of all modular fraud detection rules,
    aggregates score points, resolves risk bands, and persists alerts.
    """

    def __init__(self):
        # Register rule handlers by rule_code
        self.registry: Dict[str, BaseFraudRule] = {
            "RULE_HIGH_VALUE": HighValueTransactionRule(),
            "RULE_VELOCITY": TransactionVelocityRule(),
            "RULE_UNUSUAL_TIMING": UnusualTransactionTimingRule(),
            "RULE_GEO_ANOMALY": GeographicAnomalyRule(),
            "RULE_UNUSUAL_SPENDING": UnusualSpendingRule(),
        }

    def get_registered_codes(self) -> List[str]:
        return list(self.registry.keys())

    def validate_risk_bands(self, bands: List[Tuple[str, int, int]]) -> bool:
        """
        Validates that risk score bands cover 0 to MAX_RISK_SCORE continuously
        without gaps or overlaps.
        """
        sorted_bands = sorted(bands, key=lambda x: x[1])
        if not sorted_bands:
            return False
        if sorted_bands[0][1] != 0:
            return False
        for i in range(len(sorted_bands) - 1):
            curr_max = sorted_bands[i][2]
            next_min = sorted_bands[i + 1][1]
            if next_min != curr_max + 1:
                return False
        if sorted_bands[-1][2] < settings.MAX_RISK_SCORE:
            return False
        return True

    def determine_risk_category(self, score: int, db: Optional[Session] = None) -> str:
        """
        Map numerical score to configurable categorical band (LOW, MEDIUM, HIGH, CRITICAL).
        """
        # Attempt to load custom bands from DB if available
        if db:
            try:
                configs = db.query(RiskScoreConfiguration).all()
                if configs:
                    for cfg in configs:
                        if cfg.min_score <= score <= cfg.max_score:
                            return cfg.category_name
            except Exception as e:
                logger.warning(f"Failed to read RiskScoreConfiguration from DB, using fallback: {e}")

        # Fallback to standard calibrated bands
        if score <= settings.LOW_RISK_MAX:
            return "LOW"
        elif score <= settings.MEDIUM_RISK_MAX:
            return "MEDIUM"
        elif score <= settings.HIGH_RISK_MAX:
            return "HIGH"
        else:
            return "CRITICAL"

    def evaluate_transaction(
        self,
        transaction: Transaction,
        db: Session,
        force_reevaluate: bool = False
    ) -> Tuple[int, str, List[RuleEvaluationResult], Optional[Alert]]:
        """
        Evaluates a single transaction against all enabled rules.
        Creates or updates alert records cleanly and deterministically.
        """
        # Load rule configurations from DB
        db_rules = {r.rule_code: r for r in db.query(FraudRule).all()}

        results: List[RuleEvaluationResult] = []
        total_points = 0

        for rule_code, handler in self.registry.items():
            rule_model = db_rules.get(rule_code)

            # Check if rule is disabled in database
            if rule_model and not rule_model.is_enabled:
                continue

            params = rule_model.parameters_json if rule_model else {}
            pts = rule_model.risk_points if rule_model else handler.default_points

            try:
                eval_result = handler.evaluate(
                    transaction=transaction,
                    db=db,
                    parameters=params,
                    configured_points=pts
                )
                results.append(eval_result)
                if eval_result.triggered:
                    total_points += eval_result.points
            except Exception as exc:
                logger.error(f"Error evaluating rule {rule_code} on txn {transaction.transaction_id}: {exc}")
                results.append(
                    RuleEvaluationResult(
                        rule_code=rule_code,
                        rule_name=handler.rule_name,
                        triggered=False,
                        points=0,
                        reason=f"Evaluation failed due to internal error: {str(exc)}",
                        context={"exception": str(exc)}
                    )
                )

        # Cap score at MAX_RISK_SCORE (100)
        final_score = min(total_points, settings.MAX_RISK_SCORE)
        risk_category = self.determine_risk_category(final_score, db)

        # Mark transaction evaluated
        transaction.is_evaluated = True
        transaction.evaluated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        alert = None
        triggered_results = [r for r in results if r.triggered]

        # Check existing alert
        existing_alert = db.query(Alert).filter(Alert.transaction_id == transaction.transaction_id).first()

        if triggered_results:
            # We have triggered rules -> Create or update alert
            if existing_alert:
                if force_reevaluate:
                    # Update existing alert
                    existing_alert.risk_score = final_score
                    existing_alert.risk_category = risk_category
                    existing_alert.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    # Remove old triggers
                    db.query(AlertRuleTrigger).filter(AlertRuleTrigger.alert_id == existing_alert.alert_id).delete()
                    alert = existing_alert
                else:
                    # Keep existing alert as is
                    alert = existing_alert
            else:
                alert_ref = f"ALT-{transaction.timestamp.strftime('%Y%m')}-{transaction.transaction_id:05d}"
                alert = Alert(
                    alert_ref=alert_ref,
                    transaction_id=transaction.transaction_id,
                    risk_score=final_score,
                    risk_category=risk_category,
                    status="OPEN"
                )
                db.add(alert)
                db.flush()  # assign alert_id

            # Save trigger details for explainability
            if (not existing_alert) or force_reevaluate:
                for tr in triggered_results:
                    rule_obj = db_rules.get(tr.rule_code)
                    rule_id = rule_obj.rule_id if rule_obj else 1
                    trigger_record = AlertRuleTrigger(
                        alert_id=alert.alert_id,
                        rule_id=rule_id,
                        rule_code=tr.rule_code,
                        rule_name=tr.rule_name,
                        points_awarded=tr.points,
                        trigger_reason=tr.reason,
                        evaluation_context_json=tr.context
                    )
                    db.add(trigger_record)

        elif existing_alert and force_reevaluate:
            # If reevaluation produced 0 triggers, remove previously triggered alert
            db.delete(existing_alert)
            alert = None

        db.commit()
        return final_score, risk_category, results, alert


# Global engine instance
rule_engine = FraudDetectionEngine()
