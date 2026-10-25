from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class CustomerBase(BaseModel):
    customer_ref: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    risk_segment: str = "STANDARD"
    account_status: str = "ACTIVE"

class CustomerCreate(CustomerBase):
    pass

class CustomerOut(CustomerBase):
    customer_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class CustomerDetail(CustomerOut):
    account_count: int = 0
    total_balance: float = 0.0
    alert_count: int = 0
