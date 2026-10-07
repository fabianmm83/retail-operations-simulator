"""Schemas Pydantic para clientes (M3)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import (
    ChannelPreference,
    CustomerProfile,
    GenderType,
    PriceSensitivity,
    RecordStatus,
    SegmentType,
)


# =============================================================================
# CUSTOMER
# =============================================================================


class CustomerBase(BaseModel):
    customer_code: str = Field(..., max_length=20)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: str = Field(..., max_length=20)
    birth_date: date
    gender: GenderType
    state_id: uuid.UUID
    city: str = Field(..., max_length=100)
    postal_code: str = Field(..., max_length=10)
    profile: CustomerProfile = CustomerProfile.NEW
    channel_preference: ChannelPreference
    preferred_segment: SegmentType
    price_sensitivity: PriceSensitivity
    signup_date: date
    first_order_date: date | None = None
    last_order_date: date | None = None
    total_orders: int = Field(default=0, ge=0)
    total_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    total_units: int = Field(default=0, ge=0)
    status: RecordStatus = RecordStatus.ACTIVE


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# CUSTOMER CATEGORY PREFERENCE
# =============================================================================


class CustomerCategoryPreferenceBase(BaseModel):
    customer_id: uuid.UUID
    category_id: uuid.UUID
    preference_weight: Decimal = Field(default=Decimal("1.0"), gt=0)


class CustomerCategoryPreferenceCreate(CustomerCategoryPreferenceBase):
    pass


class CustomerCategoryPreferenceRead(CustomerCategoryPreferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomerReadWithPreferences(CustomerRead):
    category_preferences: list[CustomerCategoryPreferenceRead] = []