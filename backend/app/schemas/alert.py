from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class InvestigationNoteCreate(BaseModel):
    author: str = Field(default="Risk Analyst", min_length=2, max_length=60)
    note_text: str = Field(..., min_length=3)
    action_taken: Optional[str] = None

class InvestigationNoteOut(BaseModel):
    note_id: int
    alert_id: int
    author: str
    note_text: str
    action_taken: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class AlertStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|UNDER_INVESTIGATION|RESOLVED)$")
    resolution_reason: Optional[str] = Field(None, pattern="^(FALSE_POSITIVE|CONFIRMED_SUSPICIOUS|CUSTOMER_VERIFIED|ESCALATED|)$")
    assigned_to: Optional[str] = None
    note: Optional[str] = None

class AlertRuleTriggerOut(BaseModel):
    trigger_id: int
    rule_code: str
    rule_name: str
    points_awarded: int
    trigger_reason: str
    evaluation_context_json: Dict[str, Any]
    created_at: datetime
    model_config = {"from_attributes": True}

class AlertOut(BaseModel):
    alert_id: int
    alert_ref: str
    transaction_id: int
    risk_score: int
    risk_category: str
    status: str
    resolution_reason: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Linked Transaction Information
    transaction_ref: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    transaction_type: Optional[str] = None
    channel: Optional[str] = None
    transaction_timestamp: Optional[datetime] = None
    location_city: Optional[str] = None
    account_number: Optional[str] = None
    customer_ref: Optional[str] = None
    customer_name: Optional[str] = None
    model_config = {"from_attributes": True}

class AlertDetailOut(AlertOut):
    triggers: List[AlertRuleTriggerOut] = []
    notes: List[InvestigationNoteOut] = []

class AlertListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AlertOut]
