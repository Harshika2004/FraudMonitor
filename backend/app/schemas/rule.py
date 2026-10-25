from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class RuleBase(BaseModel):
    rule_code: str
    rule_name: str
    description: str
    rule_type: str
    parameters_json: Dict[str, Any]
    risk_points: int = Field(..., ge=1, le=100)
    is_enabled: bool = True

class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    description: Optional[str] = None
    parameters_json: Optional[Dict[str, Any]] = None
    risk_points: Optional[int] = Field(None, ge=1, le=100)
    is_enabled: Optional[bool] = None

class RuleOut(RuleBase):
    rule_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
