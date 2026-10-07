"""Endpoints read-only de sales + logistics (M6)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.sales import (
    Carrier,
    Order,
    OrderItem,
    Return,
    ReturnItem,
    Shipment,
)
from app.schemas.sales import (
    CarrierRead,
    OrderItemRead,
    OrderRead,
    OrderReadWithItems,
    ReturnItemRead,
    ReturnRead,
    ReturnReadWithItems,
    ShipmentRead,
)


router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


# =============================================================================
# CARRIERS
# =============================================================================


@router.get(
    "/carriers",
    response_model=list[CarrierRead],
    summary="Listar carriers",
)
def list_carriers(
    db: Session = Depends(get_db),
    coverage: str | None = Query(default=None),
) -> list[Carrier]:
    stmt = select(Carrier).order_by(Carrier.carrier_code)

    if coverage is not None:
        stmt = stmt.where(Carrier.coverage == coverage)

    return list(db.scalars(stmt).all())


# =============================================================================
# ORDERS
# =============================================================================


@router.get(
    "/orders",
    response_model=list[OrderRead],
    summary="Listar órdenes",
)
def list_orders(
    db: Session = Depends(get_db),
    customer_id: uuid.UUID | None = Query(default=None),
    state_id: uuid.UUID | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    channel: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Order]:
    stmt = select(Order).order_by(Order.order_date.desc())

    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    if state_id is not None:
        stmt = stmt.where(Order.state_id == state_id)
    if location_id is not None:
        stmt = stmt.where(Order.location_id == location_id)
    if channel is not None:
        stmt = stmt.where(Order.channel == channel)
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/orders/{order_id}",
    response_model=OrderReadWithItems,
    summary="Obtener una orden con sus items",
)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


# =============================================================================
# ORDER ITEMS
# =============================================================================


@router.get(
    "/order-items",
    response_model=list[OrderItemRead],
    summary="Listar items de órdenes",
)
def list_order_items(
    db: Session = Depends(get_db),
    order_id: uuid.UUID | None = Query(default=None),
    variant_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[OrderItem]:
    stmt = select(OrderItem)

    if order_id is not None:
        stmt = stmt.where(OrderItem.order_id == order_id)
    if variant_id is not None:
        stmt = stmt.where(OrderItem.variant_id == variant_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# SHIPMENTS
# =============================================================================


@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="Listar shipments",
)
def list_shipments(
    db: Session = Depends(get_db),
    order_id: uuid.UUID | None = Query(default=None),
    carrier_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Shipment]:
    stmt = select(Shipment).order_by(Shipment.shipped_at.desc().nullslast())

    if order_id is not None:
        stmt = stmt.where(Shipment.order_id == order_id)
    if carrier_id is not None:
        stmt = stmt.where(Shipment.carrier_id == carrier_id)
    if status_filter is not None:
        stmt = stmt.where(Shipment.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# RETURNS
# =============================================================================


@router.get(
    "/returns",
    response_model=list[ReturnRead],
    summary="Listar returns",
)
def list_returns(
    db: Session = Depends(get_db),
    order_id: uuid.UUID | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Return]:
    stmt = select(Return).order_by(Return.return_date.desc())

    if order_id is not None:
        stmt = stmt.where(Return.order_id == order_id)
    if customer_id is not None:
        stmt = stmt.where(Return.customer_id == customer_id)
    if status_filter is not None:
        stmt = stmt.where(Return.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/returns/{return_id}",
    response_model=ReturnReadWithItems,
    summary="Obtener un return con sus items",
)
def get_return(
    return_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Return:
    ret = db.get(Return, return_id)
    if ret is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found",
        )
    return ret


# =============================================================================
# RETURN ITEMS
# =============================================================================


@router.get(
    "/return-items",
    response_model=list[ReturnItemRead],
    summary="Listar items de returns",
)
def list_return_items(
    db: Session = Depends(get_db),
    return_id: uuid.UUID | None = Query(default=None),
    order_item_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ReturnItem]:
    stmt = select(ReturnItem)

    if return_id is not None:
        stmt = stmt.where(ReturnItem.return_id == return_id)
    if order_item_id is not None:
        stmt = stmt.where(ReturnItem.order_item_id == order_item_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())