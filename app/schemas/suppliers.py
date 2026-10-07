"""Schemas Pydantic para proveedores (M5)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    PurchaseOrderStatus,
    RecordStatus,
    SupplierType,
)


# =============================================================================
# SUPPLIER
# =============================================================================


class SupplierBase(BaseModel):
    supplier_code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    supplier_type: SupplierType
    state_id: uuid.UUID
    lead_time_days: int = Field(..., gt=0)
    reliability: Decimal = Field(..., ge=0.5, le=1.0)
    minimum_order_quantity: int = Field(..., gt=0)
    volume_discount: Decimal = Field(default=Decimal("0"), ge=0, le=0.5)
    cost_multiplier: Decimal = Field(default=Decimal("1.0"), gt=0)
    status: RecordStatus = RecordStatus.ACTIVE


class SupplierCreate(SupplierBase):
    pass


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# SUPPLIER PRODUCT
# =============================================================================


class SupplierProductBase(BaseModel):
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    unit_cost: Decimal = Field(..., gt=0)
    lead_time_days: int = Field(..., gt=0)
    minimum_order_quantity: int = Field(..., gt=0)
    priority: int = Field(..., ge=1, le=3)
    active: bool = True


class SupplierProductCreate(SupplierProductBase):
    pass


class SupplierProductRead(SupplierProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# PURCHASE ORDER
# =============================================================================


class PurchaseOrderBase(BaseModel):
    po_number: str = Field(..., max_length=30)
    supplier_id: uuid.UUID
    destination_location_id: uuid.UUID
    status: PurchaseOrderStatus = PurchaseOrderStatus.PENDING
    order_date: date
    expected_date: date
    received_date: date | None = None
    subtotal: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class PurchaseOrderCreate(PurchaseOrderBase):
    pass


class PurchaseOrderRead(PurchaseOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# PURCHASE ORDER ITEM
# =============================================================================


class PurchaseOrderItemBase(BaseModel):
    purchase_order_id: uuid.UUID
    product_id: uuid.UUID
    quantity_ordered: int = Field(..., gt=0)
    quantity_received: int = Field(default=0, ge=0)
    unit_cost: Decimal = Field(..., gt=0)
    subtotal: Decimal = Field(..., ge=0)


class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass


class PurchaseOrderItemRead(PurchaseOrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PurchaseOrderReadWithItems(PurchaseOrderRead):
    items: list[PurchaseOrderItemRead] = []