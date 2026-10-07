"""Schemas Pydantic para inventario (M4)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    MovementType,
    RecordStatus,
    StockStatus,
    TransferStatus,
)


# =============================================================================
# INVENTORY
# =============================================================================


class InventoryBase(BaseModel):
    variant_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int = Field(default=0, ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    max_stock: int = Field(default=0, ge=0)
    stock_status: StockStatus = StockStatus.NORMAL
    last_movement_date: date | None = None
    status: RecordStatus = RecordStatus.ACTIVE


class InventoryCreate(InventoryBase):
    pass


class InventoryRead(InventoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    available_quantity: int
    created_at: datetime
    updated_at: datetime


# =============================================================================
# INVENTORY MOVEMENT
# =============================================================================


class InventoryMovementBase(BaseModel):
    variant_id: uuid.UUID
    location_id: uuid.UUID
    movement_type: MovementType
    quantity: int
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    movement_date: date
    notes: str | None = None


class InventoryMovementCreate(InventoryMovementBase):
    pass


class InventoryMovementRead(InventoryMovementBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# TRANSFER
# =============================================================================


class TransferBase(BaseModel):
    transfer_code: str = Field(..., max_length=30)
    origin_location_id: uuid.UUID
    destination_location_id: uuid.UUID
    status: TransferStatus = TransferStatus.PENDING
    requested_date: date
    shipped_date: date | None = None
    received_date: date | None = None
    expected_arrival_date: date | None = None


class TransferCreate(TransferBase):
    pass


class TransferRead(TransferBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# TRANSFER ITEM
# =============================================================================


class TransferItemBase(BaseModel):
    transfer_id: uuid.UUID
    variant_id: uuid.UUID
    quantity_requested: int = Field(..., gt=0)
    quantity_shipped: int = Field(default=0, ge=0)
    quantity_received: int = Field(default=0, ge=0)


class TransferItemCreate(TransferItemBase):
    pass


class TransferItemRead(TransferItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TransferReadWithItems(TransferRead):
    items: list[TransferItemRead] = []