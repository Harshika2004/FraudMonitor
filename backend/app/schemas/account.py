from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class AccountBase(BaseModel):
    account_number: str
    customer_id: int
    account_type: str = "CHECKING"
    currency: str = "USD"
    current_balance: Decimal = Decimal("0.00")
    average_monthly_balance: Optional[Decimal] = Decimal("0.00")
    status: str = "ACTIVE"

class AccountCreate(AccountBase):
    pass

class AccountOut(AccountBase):
    account_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
