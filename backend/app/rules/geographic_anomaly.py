import math
from typing import Dict, Any, Optional
from datetime import timedelta
from sqlalchemy.orm import Session
from backend.app.models.transaction import Transaction
from backend.app.rules.base import BaseFraudRule, RuleEvaluationResult

class GeographicAnomalyRule(BaseFraudRule):
    """
    Rule D: Geographic Implausibility Rule (Impossible Travel Speed)
    Identifies transactions appearing in distant locations within an implausibly short interval.
    Uses the Haversine formula to calculate great-circle distance between coordinates.
    Computes implied travel speed: speed = distance / delta_hours.
    Flags transactions where required travel speed exceeds a realistic commercial threshold (default: 800 km/h).
    Does NOT flag simply because locations differ.
    """
    def __init__(self):
        super().__init__(
            rule_code="RULE_GEO_ANOMALY",
            rule_name="Geographic Implausibility (Impossible Speed)",
            default_points=40
        )

    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great circle distance between two points on Earth in kilometers."""
        radius_km = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2.0) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return radius_km * c

    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        params = parameters or {}
        speed_threshold_kmh = float(params.get("speed_threshold_kmh", 800.0))
        time_window_hours = float(params.get("time_window_hours", 12.0))
        points = configured_points if configured_points is not None else self.default_points

        # Need coordinates and timestamp
        if (
            transaction.latitude is None
            or transaction.longitude is None
            or not transaction.timestamp
            or not transaction.account_id
        ):
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason="Transaction coordinate or timestamp data is missing.",
                parameters_used={"speed_threshold_kmh": speed_threshold_kmh, "time_window_hours": time_window_hours},
                context={"warning": "missing_coordinates_or_time"}
            )

        # Look up immediate previous transaction for this account within time_window_hours
        window_start = transaction.timestamp - timedelta(hours=time_window_hours)

        prev_tx = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == transaction.account_id,
                Transaction.timestamp < transaction.timestamp,
                Transaction.timestamp >= window_start,
                Transaction.latitude.isnot(None),
                Transaction.longitude.isnot(None),
                Transaction.transaction_id != transaction.transaction_id
            )
            .order_by(Transaction.timestamp.desc())
            .first()
        )

        parameters_used = {
            "speed_threshold_kmh": speed_threshold_kmh,
            "time_window_hours": time_window_hours
        }

        if not prev_tx:
            return RuleEvaluationResult(
                rule_code=self.rule_code,
                rule_name=self.rule_name,
                triggered=False,
                points=0,
                reason=f"No prior geographic transaction found for account within the {time_window_hours}-hour window.",
                parameters_used=parameters_used,
                context={"prior_tx_found": False}
            )

        # Calculate time delta in hours
        delta_seconds = (transaction.timestamp - prev_tx.timestamp).total_seconds()
        delta_hours = max(delta_seconds / 3600.0, 0.001)  # avoid division by zero

        # Calculate distance
        lat1 = float(prev_tx.latitude)
        lon1 = float(prev_tx.longitude)
        lat2 = float(transaction.latitude)
        lon2 = float(transaction.longitude)

        distance_km = self.haversine_distance_km(lat1, lon1, lat2, lon2)
        implied_speed = distance_km / delta_hours

        # Only trigger if speed > threshold and distance is significant (> 25 km)
        is_triggered = (distance_km > 25.0) and (implied_speed > speed_threshold_kmh)

        context = {
            "current_location": f"{transaction.location_city}, {transaction.location_country}",
            "current_coords": [lat2, lon2],
            "previous_location": f"{prev_tx.location_city}, {prev_tx.location_country}",
            "previous_coords": [lat1, lon1],
            "previous_tx_ref": prev_tx.transaction_ref,
            "distance_km": round(distance_km, 2),
            "delta_hours": round(delta_hours, 3),
            "implied_speed_kmh": round(implied_speed, 2),
            "speed_threshold_kmh": speed_threshold_kmh
        }

        if is_triggered:
            reason = (
                f"Implausible travel speed detected: Transaction occurred {round(distance_km, 1)} km away "
                f"from previous transaction ({prev_tx.location_city}) in {round(delta_hours * 60, 1)} minutes, "
                f"requiring an impossible travel speed of {round(implied_speed, 1)} km/h "
                f"(exceeds maximum physical threshold of {speed_threshold_kmh} km/h)."
            )
            awarded = points
        else:
            reason = (
                f"Geographic transition from {prev_tx.location_city} to {transaction.location_city} "
                f"({round(distance_km, 1)} km in {round(delta_hours, 2)} hrs = {round(implied_speed, 1)} km/h) "
                f"is within physically plausible travel limits."
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
