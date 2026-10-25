from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class TransactionBase(BaseModel):
    account_id: int
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    transaction_type: str  # TRANSFER, DEPOSIT, WITHDRAWAL, CARD_PAYMENT, ONLINE_PURCHASE
    channel: str = "ONLINE"
    timestamp: datetime
    location_city: str
    location_country: str = "USA"
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    status: str = "COMPLETED"

class TransactionCreate(TransactionBase):
    transaction_ref: Optional[str] = None

class TransactionOut(TransactionBase):
    transaction_id: int
    transaction_ref: str
    is_evaluated: bool
    evaluated_at: Optional[datetime] = None
    created_at: datetime
    has_alert: bool = False
    alert_risk_category: Optional[str] = None
    alert_risk_score: Optional[int] = None
    account_number: Optional[str] = None
    customer_name: Optional[str] = None

    model_config = {"from_attributes": True}

class TransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TransactionOut]

class SingleTransactionEvaluationResponse(BaseModel):
    transaction_id: int
    transaction_ref: str
    is_flagged: bool
    risk_score: int
    risk_category: str
    alert_ref: Optional[str] = None
    triggers_count: int
    triggered_rules: List[dict]
    all_rule_results: List[dict]

class BatchEvaluationResponse(BaseModel):
    evaluated_count: int
    flagged_count: int
    alerts_created: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    message: str
