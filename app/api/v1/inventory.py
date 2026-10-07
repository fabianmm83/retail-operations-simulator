"""Endpoints read-only de inventario (M4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.inventory import (
    Inventory,
    InventoryMovement,
    Transfer,
    TransferItem,
)
from app.schemas.inventory import (
    InventoryMovementRead,
    InventoryRead,
    TransferItemRead,
    TransferRead,
    TransferReadWithItems,
)


router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


# =============================================================================
# INVENTORY
# =============================================================================


@router.get(
    "",
    response_model=list[InventoryRead],
    summary="Listar registros de inventario",
)
def list_inventory(
    db: Session = Depends(get_db),
    variant_id: uuid.UUID | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    stock_status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Inventory]:
    stmt = select(Inventory)

    if variant_id is not None:
        stmt = stmt.where(Inventory.variant_id == variant_id)
    if location_id is not None:
        stmt = stmt.where(Inventory.location_id == location_id)
    if stock_status is not None:
        stmt = stmt.where(Inventory.stock_status == stock_status)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# INVENTORY MOVEMENTS
# =============================================================================


@router.get(
    "/movements",
    response_model=list[InventoryMovementRead],
    summary="Listar movimientos de inventario",
)
def list_movements(
    db: Session = Depends(get_db),
    variant_id: uuid.UUID | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    movement_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[InventoryMovement]:
    stmt = select(InventoryMovement).order_by(
        InventoryMovement.movement_date.desc()
    )

    if variant_id is not None:
        stmt = stmt.where(InventoryMovement.variant_id == variant_id)
    if location_id is not None:
        stmt = stmt.where(InventoryMovement.location_id == location_id)
    if movement_type is not None:
        stmt = stmt.where(InventoryMovement.movement_type == movement_type)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# TRANSFERS
# =============================================================================


@router.get(
    "/transfers",
    response_model=list[TransferRead],
    summary="Listar transferencias",
)
def list_transfers(
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    origin_location_id: uuid.UUID | None = Query(default=None),
    destination_location_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Transfer]:
    stmt = select(Transfer).order_by(Transfer.requested_date.desc())

    if status_filter is not None:
        stmt = stmt.where(Transfer.status == status_filter)
    if origin_location_id is not None:
        stmt = stmt.where(Transfer.origin_location_id == origin_location_id)
    if destination_location_id is not None:
        stmt = stmt.where(
            Transfer.destination_location_id == destination_location_id
        )

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/transfers/{transfer_id}",
    response_model=TransferReadWithItems,
    summary="Obtener una transferencia con sus items",
)
def get_transfer(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Transfer:
    transfer = db.get(Transfer, transfer_id)
    if transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )
    return transfer


# =============================================================================
# TRANSFER ITEMS
# =============================================================================


@router.get(
    "/transfer-items",
    response_model=list[TransferItemRead],
    summary="Listar items de transferencias",
)
def list_transfer_items(
    db: Session = Depends(get_db),
    transfer_id: uuid.UUID | None = Query(default=None),
    variant_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TransferItem]:
    stmt = select(TransferItem)

    if transfer_id is not None:
        stmt = stmt.where(TransferItem.transfer_id == transfer_id)
    if variant_id is not None:
        stmt = stmt.where(TransferItem.variant_id == variant_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())