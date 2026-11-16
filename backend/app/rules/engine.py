import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from collections import defaultdict
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
                alert_ref = f"ALT-{transaction.timestamp.strftime('%Y%m')}-{transaction.transaction_id:05d}" if transaction.timestamp else f"ALT-TXN-{transaction.transaction_id:05d}"
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

    def evaluate_batch(
        self,
        db: Session,
        transactions: List[Transaction],
        force_reevaluate: bool = False
    ) -> Dict[str, Any]:
        """
        High-performance batch fraud rule evaluation for datasets.
        Evaluates transactions in-memory using indexed account histories
        and commits alerts/triggers in a single atomic database operation.
        Achieves sub-second processing for thousands of transactions.
        """
        if not transactions:
            return {
                "evaluated_count": 0,
                "flagged_count": 0,
                "alerts_created": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "cat_counts": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
                "message": "No transactions to evaluate."
            }

        # 1. Preload rules & risk score configurations
        db_rules = {r.rule_code: r for r in db.query(FraudRule).all()}
        risk_configs = []
        try:
            risk_configs = db.query(RiskScoreConfiguration).all()
        except Exception:
            pass

        def resolve_risk_category(score: int) -> str:
            if risk_configs:
                for cfg in risk_configs:
                    if cfg.min_score <= score <= cfg.max_score:
                        return cfg.category_name
            if score <= settings.LOW_RISK_MAX:
                return "LOW"
            elif score <= settings.MEDIUM_RISK_MAX:
                return "MEDIUM"
            elif score <= settings.HIGH_RISK_MAX:
                return "HIGH"
            else:
                return "CRITICAL"

        # Preload rule parameters
        rule_high = db_rules.get("RULE_HIGH_VALUE")
        high_enabled = rule_high.is_enabled if rule_high else True
        high_params = rule_high.parameters_json if rule_high else {}
        high_thresh = Decimal(str(high_params.get("threshold", 10000.00)))
        high_curr = str(high_params.get("currency", "USD"))
        high_pts = rule_high.risk_points if rule_high else 35

        rule_vel = db_rules.get("RULE_VELOCITY")
        vel_enabled = rule_vel.is_enabled if rule_vel else True
        vel_params = rule_vel.parameters_json if rule_vel else {}
        vel_win_min = int(vel_params.get("time_window_minutes", 60))
        vel_thresh = int(vel_params.get("transaction_count_threshold", 3))
        vel_pts = rule_vel.risk_points if rule_vel else 30

        rule_timing = db_rules.get("RULE_UNUSUAL_TIMING")
        timing_enabled = rule_timing.is_enabled if rule_timing else True
        timing_params = rule_timing.parameters_json if rule_timing else {}
        timing_start = int(timing_params.get("start_hour", 1))
        timing_end = int(timing_params.get("end_hour", 5))
        timing_pts = rule_timing.risk_points if rule_timing else 20

        rule_geo = db_rules.get("RULE_GEO_ANOMALY")
        geo_enabled = rule_geo.is_enabled if rule_geo else True
        geo_params = rule_geo.parameters_json if rule_geo else {}
        geo_speed_thresh = float(geo_params.get("speed_threshold_kmh", 800.0))
        geo_win_hours = float(geo_params.get("time_window_hours", 12.0))
        geo_pts = rule_geo.risk_points if rule_geo else 40

        rule_spending = db_rules.get("RULE_UNUSUAL_SPENDING")
        spending_enabled = rule_spending.is_enabled if rule_spending else True
        spending_params = rule_spending.parameters_json if rule_spending else {}
        spending_mult = float(spending_params.get("baseline_multiplier", 3.0))
        spending_min_hist = int(spending_params.get("min_historical_txns", 5))
        spending_lookback = int(spending_params.get("lookback_days", 30))
        spending_pts = rule_spending.risk_points if rule_spending else 25

        # 2. Sort transactions chronologically
        sorted_txns = sorted(transactions, key=lambda t: t.timestamp or datetime.min)
        txn_ids = [t.transaction_id for t in sorted_txns]

        # 3. Preload account histories from existing database records (prior transactions)
        account_ids = list({t.account_id for t in sorted_txns if t.account_id})
        acct_txs: Dict[int, List[Tuple[datetime, float, str, str]]] = defaultdict(list)
        acct_geo: Dict[int, List[Tuple[datetime, float, float, str, str]]] = defaultdict(list)

        if account_ids:
            prior_rows = (
                db.query(
                    Transaction.account_id,
                    Transaction.timestamp,
                    Transaction.amount,
                    Transaction.status,
                    Transaction.transaction_ref,
                    Transaction.latitude,
                    Transaction.longitude,
                    Transaction.location_city,
                    Transaction.location_country
                )
                .filter(
                    Transaction.account_id.in_(account_ids),
                    Transaction.is_evaluated == True,
                    Transaction.transaction_id.notin_(txn_ids)
                )
                .order_by(Transaction.timestamp.asc())
                .all()
            )
            for pr in prior_rows:
                acct_txs[pr[0]].append((pr[1], float(pr[2]) if pr[2] else 0.0, pr[3], pr[4]))
                if pr[5] is not None and pr[6] is not None:
                    acct_geo[pr[0]].append((pr[1], float(pr[5]), float(pr[6]), pr[7] or "", pr[8] or ""))

        # 4. Preload existing alerts for these transactions
        existing_alerts = {a.transaction_id: a for a in db.query(Alert).filter(Alert.transaction_id.in_(txn_ids)).all()}
        if existing_alerts and force_reevaluate:
            alt_ids = [a.alert_id for a in existing_alerts.values()]
            db.query(AlertRuleTrigger).filter(AlertRuleTrigger.alert_id.in_(alt_ids)).delete(synchronize_session=False)

        # 5. Evaluate all transactions in-memory
        evaluated_count = 0
        flagged_count = 0
        alerts_created = 0
        cat_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

        new_alerts = []
        new_triggers = []
        now_ts = datetime.now(timezone.utc).replace(tzinfo=None)

        for txn in sorted_txns:
            total_points = 0
            triggers_data = []

            # Rule A: High Value
            if high_enabled and txn.amount is not None:
                amt = Decimal(str(txn.amount))
                if amt >= high_thresh:
                    total_points += high_pts
                    triggers_data.append({
                        "rule_code": "RULE_HIGH_VALUE",
                        "rule_name": rule_high.rule_name if rule_high else "High-Value Transaction Threshold",
                        "points": high_pts,
                        "reason": f"Transaction amount of {amt:,.2f} {txn.currency or high_curr} meets or exceeds the configured threshold of {high_thresh:,.2f} {high_curr}.",
                        "context": {"amount": float(amt), "threshold": float(high_thresh), "currency": txn.currency or high_curr}
                    })

            # Rule B: Velocity
            if vel_enabled and txn.timestamp and txn.account_id:
                win_start = txn.timestamp - timedelta(minutes=vel_win_min)
                hist = acct_txs[txn.account_id]
                in_win = [h for h in hist if win_start <= h[0] <= txn.timestamp]
                count_in_win = len(in_win) + 1  # include current txn
                if count_in_win >= vel_thresh:
                    total_points += vel_pts
                    triggers_data.append({
                        "rule_code": "RULE_VELOCITY",
                        "rule_name": rule_vel.rule_name if rule_vel else "High Transaction Velocity",
                        "points": vel_pts,
                        "reason": f"Account processed {count_in_win} transactions within {vel_win_min} minutes, exceeding velocity threshold of {vel_thresh}.",
                        "context": {
                            "account_id": txn.account_id,
                            "window_minutes": vel_win_min,
                            "count_in_window": count_in_win,
                            "threshold": vel_thresh,
                            "transactions_in_window": [h[3] for h in in_win] + [txn.transaction_ref]
                        }
                    })

            # Rule C: Timing
            if timing_enabled and txn.timestamp:
                hr = txn.timestamp.hour
                is_off = (timing_start <= hr <= timing_end) if timing_start <= timing_end else (hr >= timing_start or hr <= timing_end)
                if is_off:
                    total_points += timing_pts
                    triggers_data.append({
                        "rule_code": "RULE_UNUSUAL_TIMING",
                        "rule_name": rule_timing.rule_name if rule_timing else "Unusual Transaction Timing",
                        "points": timing_pts,
                        "reason": f"Transaction initiated at off-hours: {hr:02d}:00 (configured off-hours: {timing_start:02d}:00 - {timing_end:02d}:59).",
                        "context": {
                            "transaction_timestamp": txn.timestamp.isoformat(),
                            "transaction_hour": hr,
                            "monitored_start_hour": timing_start,
                            "monitored_end_hour": timing_end
                        }
                    })

            # Rule D: Geo Anomaly
            if geo_enabled and txn.latitude is not None and txn.longitude is not None and txn.timestamp and txn.account_id:
                win_start_geo = txn.timestamp - timedelta(hours=geo_win_hours)
                geo_hist = acct_geo[txn.account_id]
                if geo_hist:
                    prev = geo_hist[-1]
                    if prev[0] >= win_start_geo and prev[0] < txn.timestamp:
                        delta_hrs = max((txn.timestamp - prev[0]).total_seconds() / 3600.0, 0.001)
                        dist = GeographicAnomalyRule.haversine_distance_km(prev[1], prev[2], float(txn.latitude), float(txn.longitude))
                        speed = dist / delta_hrs
                        if dist > 25.0 and speed > geo_speed_thresh:
                            total_points += geo_pts
                            triggers_data.append({
                                "rule_code": "RULE_GEO_ANOMALY",
                                "rule_name": rule_geo.rule_name if rule_geo else "Geographic Implausibility (Impossible Speed)",
                                "points": geo_pts,
                                "reason": f"Implausible travel speed of {speed:.1f} km/h detected between consecutive transactions separated by {dist:.1f} km in {delta_hrs:.2f} hours.",
                                "context": {
                                    "current_location": f"{txn.location_city}, {txn.location_country}",
                                    "current_coords": [float(txn.latitude), float(txn.longitude)],
                                    "previous_location": f"{prev[3]}, {prev[4]}",
                                    "previous_coords": [prev[1], prev[2]],
                                    "distance_km": round(dist, 2),
                                    "time_delta_hours": round(delta_hrs, 2),
                                    "implied_speed_kmh": round(speed, 1),
                                    "speed_threshold_kmh": geo_speed_thresh
                                }
                            })

            # Rule E: Unusual Spending
            if spending_enabled and txn.amount is not None and txn.timestamp and txn.account_id:
                look_start = txn.timestamp - timedelta(days=spending_lookback)
                curr_amt = float(txn.amount)
                prior_completed = [h[1] for h in acct_txs[txn.account_id] if h[0] < txn.timestamp and h[0] >= look_start and h[2] == "COMPLETED"]
                if len(prior_completed) >= spending_min_hist:
                    mean = sum(prior_completed) / len(prior_completed)
                    if curr_amt > spending_mult * mean:
                        ratio = round(curr_amt / mean, 2)
                        total_points += spending_pts
                        triggers_data.append({
                            "rule_code": "RULE_UNUSUAL_SPENDING",
                            "rule_name": rule_spending.rule_name if rule_spending else "Deviant Spending vs Historical Baseline",
                            "points": spending_pts,
                            "reason": f"Transaction amount of {curr_amt:,.2f} is {ratio:.1f}x the historical average of {mean:,.2f} (threshold: {spending_mult}x).",
                            "context": {
                                "current_amount": curr_amt,
                                "historical_mean": round(mean, 2),
                                "multiplier_used": spending_mult,
                                "deviation_ratio": ratio,
                                "historical_transaction_count": len(prior_completed)
                            }
                        })

            # Update in-memory account history
            acct_txs[txn.account_id].append((txn.timestamp, float(txn.amount) if txn.amount else 0.0, txn.status, txn.transaction_ref))
            if txn.latitude is not None and txn.longitude is not None:
                acct_geo[txn.account_id].append((txn.timestamp, float(txn.latitude), float(txn.longitude), txn.location_city or "", txn.location_country or ""))

            # Final score & category
            final_score = min(total_points, settings.MAX_RISK_SCORE)
            risk_category = resolve_risk_category(final_score)

            txn.is_evaluated = True
            txn.evaluated_at = now_ts
            evaluated_count += 1
            cat_counts[risk_category] = cat_counts.get(risk_category, 0) + 1

            # Handle alert
            existing_alt = existing_alerts.get(txn.transaction_id)
            if triggers_data:
                flagged_count += 1
                if existing_alt:
                    existing_alt.risk_score = final_score
                    existing_alt.risk_category = risk_category
                    existing_alt.updated_at = now_ts
                    for tr in triggers_data:
                        r_obj = db_rules.get(tr["rule_code"])
                        r_id = r_obj.rule_id if r_obj else 1
                        new_triggers.append(AlertRuleTrigger(
                            alert_id=existing_alt.alert_id,
                            rule_id=r_id,
                            rule_code=tr["rule_code"],
                            rule_name=tr["rule_name"],
                            points_awarded=tr["points"],
                            trigger_reason=tr["reason"],
                            evaluation_context_json=tr["context"]
                        ))
                else:
                    alt_ref = f"ALT-{txn.timestamp.strftime('%Y%m')}-{txn.transaction_id:05d}" if txn.timestamp else f"ALT-TXN-{txn.transaction_id:05d}"
                    new_alt = Alert(
                        alert_ref=alt_ref,
                        transaction_id=txn.transaction_id,
                        risk_score=final_score,
                        risk_category=risk_category,
                        status="OPEN"
                    )
                    new_alt._pending_triggers = triggers_data
                    new_alerts.append(new_alt)
                    alerts_created += 1
            elif existing_alt and force_reevaluate:
                db.delete(existing_alt)

        # 6. Save all alerts and triggers in a single batch
        if new_alerts:
            db.add_all(new_alerts)
            db.flush()
            for alt in new_alerts:
                for tr in getattr(alt, "_pending_triggers", []):
                    r_obj = db_rules.get(tr["rule_code"])
                    r_id = r_obj.rule_id if r_obj else 1
                    new_triggers.append(AlertRuleTrigger(
                        alert_id=alt.alert_id,
                        rule_id=r_id,
                        rule_code=tr["rule_code"],
                        rule_name=tr["rule_name"],
                        points_awarded=tr["points"],
                        trigger_reason=tr["reason"],
                        evaluation_context_json=tr["context"]
                    ))

        if new_triggers:
            db.add_all(new_triggers)

        db.commit()

        return {
            "evaluated_count": evaluated_count,
            "flagged_count": flagged_count,
            "alerts_created": alerts_created,
            "critical_count": cat_counts.get("CRITICAL", 0),
            "high_count": cat_counts.get("HIGH", 0),
            "medium_count": cat_counts.get("MEDIUM", 0),
            "low_count": cat_counts.get("LOW", 0),
            "cat_counts": cat_counts,
            "message": f"Successfully evaluated {evaluated_count:,} transactions. Flagged {flagged_count:,} suspicious items."
        }

# Global engine instance
rule_engine = FraudDetectionEngine()
