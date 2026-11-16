import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from backend.app.models.dataset import Dataset
from backend.app.models.transaction import Transaction
from backend.app.models.alert import Alert, AlertRuleTrigger
from backend.app.models.rule import FraudRule
from backend.app.schemas.analytics import (
    DashboardAnalyticsResponse,
    KPISummary,
    CategoryCount,
    RuleTriggerStat,
    DailyTrendPoint,
    ChannelDistribution
)

logger = logging.getLogger(__name__)

class AnalyticsAggregator:

    @staticmethod
    def get_dashboard_analytics(
        db: Session,
        days: int = 30,
        dataset_id: Optional[int] = None
    ) -> DashboardAnalyticsResponse:
        """
        Calculates end-to-end dashboard analytics and metrics from actual database records.
        Filters by the specified dataset_id or the currently active dataset.
        """
        if dataset_id is None:
            active_ds = db.query(Dataset).filter(Dataset.is_active == True).first()
            if active_ds:
                dataset_id = active_ds.dataset_id

        # KPI calculations
        total_txns_q = db.query(func.count(Transaction.transaction_id))
        eval_txns_q = db.query(func.count(Transaction.transaction_id)).filter(Transaction.is_evaluated == True)
        tot_vol_q = db.query(func.sum(Transaction.amount))

        if dataset_id is not None:
            total_txns_q = total_txns_q.filter(Transaction.dataset_id == dataset_id)
            eval_txns_q = eval_txns_q.filter(Transaction.dataset_id == dataset_id)
            tot_vol_q = tot_vol_q.filter(Transaction.dataset_id == dataset_id)

        total_txns = total_txns_q.scalar() or 0
        evaluated_txns = eval_txns_q.scalar() or 0
        total_volume_raw = tot_vol_q.scalar() or Decimal('0.00')
        total_volume = float(total_volume_raw)

        # Alerts summary (scoped by dataset through transaction join)
        def alert_base_q():
            q = db.query(func.count(Alert.alert_id)).join(Transaction, Alert.transaction_id == Transaction.transaction_id)
            if dataset_id is not None:
                q = q.filter(Transaction.dataset_id == dataset_id)
            return q

        total_alerts = alert_base_q().scalar() or 0
        open_alerts = alert_base_q().filter(Alert.status == "OPEN").scalar() or 0
        under_inv = alert_base_q().filter(Alert.status == "UNDER_INVESTIGATION").scalar() or 0
        resolved_alerts = alert_base_q().filter(Alert.status == "RESOLVED").scalar() or 0
        high_critical = alert_base_q().filter(Alert.risk_category.in_(["HIGH", "CRITICAL"])).scalar() or 0

        # Flagged transactions volume
        flagged_vol_q = (
            db.query(func.sum(Transaction.amount))
            .join(Alert, Transaction.transaction_id == Alert.transaction_id)
        )
        if dataset_id is not None:
            flagged_vol_q = flagged_vol_q.filter(Transaction.dataset_id == dataset_id)
        flagged_vol_raw = flagged_vol_q.scalar() or Decimal('0.00')
        flagged_volume = float(flagged_vol_raw)

        flagged_txns = total_alerts
        flag_rate = round((flagged_txns / evaluated_txns * 100.0), 2) if evaluated_txns > 0 else 0.0

        kpi = KPISummary(
            total_transactions=total_txns,
            evaluated_transactions=evaluated_txns,
            flagged_transactions=flagged_txns,
            flag_rate_percentage=flag_rate,
            total_alerts=total_alerts,
            open_alerts=open_alerts,
            under_investigation_alerts=under_inv,
            resolved_alerts=resolved_alerts,
            high_critical_alerts=high_critical,
            total_monitored_volume=round(total_volume, 2),
            flagged_volume=round(flagged_volume, 2)
        )

        # Risk distribution
        cat_colors = {
            "LOW": "#10b981",       # Emerald Green
            "MEDIUM": "#f59e0b",    # Amber
            "HIGH": "#f97316",      # Orange
            "CRITICAL": "#ef4444"   # Red
        }
        risk_counts_q = (
            db.query(Alert.risk_category, func.count(Alert.alert_id))
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
        )
        if dataset_id is not None:
            risk_counts_q = risk_counts_q.filter(Transaction.dataset_id == dataset_id)
        risk_counts = risk_counts_q.group_by(Alert.risk_category).all()
        risk_map = {row[0]: row[1] for row in risk_counts}
        risk_distribution = [
            CategoryCount(category=cat, count=risk_map.get(cat, 0), color=cat_colors.get(cat, "#64748b"))
            for cat in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        ]

        # Alert status distribution
        status_colors = {
            "OPEN": "#ef4444",
            "UNDER_INVESTIGATION": "#3b82f6",
            "RESOLVED": "#10b981"
        }
        status_counts_q = (
            db.query(Alert.status, func.count(Alert.alert_id))
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
        )
        if dataset_id is not None:
            status_counts_q = status_counts_q.filter(Transaction.dataset_id == dataset_id)
        status_counts = status_counts_q.group_by(Alert.status).all()
        status_map = {row[0]: row[1] for row in status_counts}
        status_distribution = [
            CategoryCount(category=st, count=status_map.get(st, 0), color=status_colors.get(st, "#64748b"))
            for st in ["OPEN", "UNDER_INVESTIGATION", "RESOLVED"]
        ]

        # Rule frequency
        rule_stats_q = (
            db.query(
                AlertRuleTrigger.rule_code,
                AlertRuleTrigger.rule_name,
                func.count(AlertRuleTrigger.trigger_id).label("cnt"),
                func.avg(AlertRuleTrigger.points_awarded).label("avg_pts")
            )
            .join(Alert, AlertRuleTrigger.alert_id == Alert.alert_id)
            .join(Transaction, Alert.transaction_id == Transaction.transaction_id)
        )
        if dataset_id is not None:
            rule_stats_q = rule_stats_q.filter(Transaction.dataset_id == dataset_id)
        rule_stats_query = (
            rule_stats_q
            .group_by(AlertRuleTrigger.rule_code, AlertRuleTrigger.rule_name)
            .order_by(desc("cnt"))
            .all()
        )
        rule_frequency = [
            RuleTriggerStat(
                rule_code=row[0],
                rule_name=row[1],
                trigger_count=row[2],
                avg_points=round(float(row[3]), 1) if row[3] is not None else 0.0
            )
            for row in rule_stats_query
        ]

        # Daily trends using Pandas for robust timeseries aggregation
        # days=0 means "all transactions" — no date filter applied
        recent_txs_q = (
            db.query(
                Transaction.transaction_id,
                Transaction.timestamp,
                Transaction.amount,
                Alert.alert_id
            )
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
        )
        if days > 0:
            start_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            recent_txs_q = recent_txs_q.filter(Transaction.timestamp >= start_date)
        if dataset_id is not None:
            recent_txs_q = recent_txs_q.filter(Transaction.dataset_id == dataset_id)
        recent_txs = recent_txs_q.all()

        daily_trends = []
        if recent_txs:
            df = pd.DataFrame([
                {
                    "date": r[1].strftime("%Y-%m-%d"),
                    "amount": float(r[2]),
                    "is_flagged": 1 if r[3] is not None else 0,
                    "flagged_amount": float(r[2]) if r[3] is not None else 0.0
                }
                for r in recent_txs
            ])
            grouped = df.groupby("date").agg({
                "amount": ["count", "sum"],
                "is_flagged": "sum",
                "flagged_amount": "sum"
            }).reset_index()
            grouped.columns = ["date", "total_count", "total_amount", "flagged_count", "flagged_amount"]
            grouped = grouped.sort_values("date")

            for _, row in grouped.iterrows():
                daily_trends.append(DailyTrendPoint(
                    date=str(row["date"]),
                    total_count=int(row["total_count"]),
                    flagged_count=int(row["flagged_count"]),
                    total_amount=round(float(row["total_amount"]), 2),
                    flagged_amount=round(float(row["flagged_amount"]), 2)
                ))

        # Channel distribution
        channel_q = (
            db.query(
                Transaction.channel,
                func.count(Transaction.transaction_id).label("total_tx"),
                func.count(Alert.alert_id).label("alert_cnt")
            )
            .outerjoin(Alert, Transaction.transaction_id == Alert.transaction_id)
        )
        if dataset_id is not None:
            channel_q = channel_q.filter(Transaction.dataset_id == dataset_id)
        channel_query = channel_q.group_by(Transaction.channel).all()
        channel_breakdown = [
            ChannelDistribution(
                channel=row[0],
                transaction_count=row[1],
                alert_count=row[2]
            )
            for row in channel_query
        ]

        return DashboardAnalyticsResponse(
            kpi=kpi,
            risk_distribution=risk_distribution,
            alert_status_distribution=status_distribution,
            rule_frequency=rule_frequency,
            daily_trends=daily_trends,
            channel_breakdown=channel_breakdown
        )
