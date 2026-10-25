from pydantic import BaseModel
from typing import List, Dict, Any

class KPISummary(BaseModel):
    total_transactions: int
    evaluated_transactions: int
    flagged_transactions: int
    flag_rate_percentage: float
    total_alerts: int
    open_alerts: int
    under_investigation_alerts: int
    resolved_alerts: int
    high_critical_alerts: int
    total_monitored_volume: float
    flagged_volume: float

class CategoryCount(BaseModel):
    category: str
    count: int
    color: str

class RuleTriggerStat(BaseModel):
    rule_code: str
    rule_name: str
    trigger_count: int
    avg_points: float

class DailyTrendPoint(BaseModel):
    date: str
    total_count: int
    flagged_count: int
    total_amount: float
    flagged_amount: float

class ChannelDistribution(BaseModel):
    channel: str
    transaction_count: int
    alert_count: int

class DashboardAnalyticsResponse(BaseModel):
    kpi: KPISummary
    risk_distribution: List[CategoryCount]
    alert_status_distribution: List[CategoryCount]
    rule_frequency: List[RuleTriggerStat]
    daily_trends: List[DailyTrendPoint]
    channel_breakdown: List[ChannelDistribution]
