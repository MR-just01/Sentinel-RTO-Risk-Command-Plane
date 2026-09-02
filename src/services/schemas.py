"""
Pydantic Request and Response Schemas for the Sentinel-RTO API.
"""
from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, Field


class OrderEvaluationRequest(BaseModel):
    order_id: str
    user_id: str
    phone: str
    device_id: str
    ip_address: str
    delivery_address: str
    city: str
    pincode: str
    pincode_tier: int = Field(default=1, ge=1, le=3)
    category: str
    order_value_inr: float = Field(..., gt=0)
    item_count: int = Field(default=1, ge=1)
    payment_method: str = "COD"
    is_first_time_user: int = Field(default=1, ge=0, le=1)
    created_at: Optional[datetime] = None


class RiskDriver(BaseModel):
    feature: str
    impact_score: float
    current_value: Union[float, str, int]


class OrderEvaluationResponse(BaseModel):
    order_id: str
    risk_probability: float
    risk_tier: str
    action: str
    action_payload: dict
    risk_drivers: list[RiskDriver]
    execution_time_ms: float