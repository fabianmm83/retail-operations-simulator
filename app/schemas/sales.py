"""Schemas Pydantic para sales + logistics (M6)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    CarrierCoverage,
    OrderChannel,
    OrderStatus,
    PaymentMethod,
    RecordStatus,
    ReturnItemCondition,
    ReturnReason,
    ReturnStatus,
    ShipmentStatus,
)


# =============================================================================
# CARRIER
# =============================================================================


class CarrierBase(BaseModel):
    carrier_code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    coverage: CarrierCoverage
    base_lead_time_days: int = Field(..., gt=0)
    max_lead_time_days: int = Field(..., gt=0)
    reliability: Decimal = Field(..., ge=0.5, le=1.0)
    base_cost: Decimal = Field(..., ge=0)
    cost_multiplier: Decimal = Field(default=Decimal("1.0"), gt=0)
    status: RecordStatus = RecordStatus.ACTIVE


class CarrierCreate(CarrierBase):
    pass


class CarrierRead(CarrierBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# ORDER
# =============================================================================


class OrderBase(BaseModel):
    order_number: str = Field(..., max_length=30)
    customer_id: uuid.UUID
    state_id: uuid.UUID
    location_id: uuid.UUID
    channel: OrderChannel
    status: OrderStatus = OrderStatus.PENDING
    order_date: date
    payment_method: PaymentMethod
    paid: bool = False
    subtotal: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(default=Decimal("0"), ge=0)


class OrderCreate(OrderBase):
    pass


class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# ORDER ITEM
# =============================================================================


class OrderItemBase(BaseModel):
    order_id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    subtotal: Decimal = Field(..., ge=0)


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemRead(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OrderReadWithItems(OrderRead):
    items: list[OrderItemRead] = []


# =============================================================================
# SHIPMENT
# =============================================================================


class ShipmentBase(BaseModel):
    shipment_number: str = Field(..., max_length=30)
    tracking_number: str = Field(..., max_length=50)
    order_id: uuid.UUID
    carrier_id: uuid.UUID
    origin_location_id: uuid.UUID
    status: ShipmentStatus = ShipmentStatus.PENDING
    shipped_at: date | None = None
    estimated_delivery: date | None = None
    delivered_at: date | None = None
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    weight_kg: Decimal = Field(default=Decimal("0"), ge=0)


class ShipmentCreate(ShipmentBase):
    pass


class ShipmentRead(ShipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OrderReadWithShipments(OrderRead):
    shipments: list[ShipmentRead] = []


# =============================================================================
# RETURN
# =============================================================================


class ReturnBase(BaseModel):
    order_id: uuid.UUID
    customer_id: uuid.UUID
    status: ReturnStatus = ReturnStatus.REQUESTED
    reason: ReturnReason
    return_date: date
    received_date: date | None = None
    refund_date: date | None = None
    refund_amount: Decimal = Field(default=Decimal("0"), ge=0)


class ReturnCreate(ReturnBase):
    pass


class ReturnRead(ReturnBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# RETURN ITEM
# =============================================================================


class ReturnItemBase(BaseModel):
    return_id: uuid.UUID
    order_item_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    condition: ReturnItemCondition


class ReturnItemCreate(ReturnItemBase):
    pass


class ReturnItemRead(ReturnItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ReturnReadWithItems(ReturnRead):
    items: list[ReturnItemRead] = []