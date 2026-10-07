"""Endpoints read-only de proveedores (M5)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.suppliers import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierProduct,
)
from app.schemas.suppliers import (
    PurchaseOrderItemRead,
    PurchaseOrderRead,
    PurchaseOrderReadWithItems,
    SupplierProductRead,
    SupplierRead,
)


router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


# =============================================================================
# SUPPLIERS
# =============================================================================


@router.get(
    "",
    response_model=list[SupplierRead],
    summary="Listar proveedores",
)
def list_suppliers(
    db: Session = Depends(get_db),
    supplier_type: str | None = Query(default=None),
) -> list[Supplier]:
    stmt = select(Supplier).order_by(Supplier.supplier_code)

    if supplier_type is not None:
        stmt = stmt.where(Supplier.supplier_type == supplier_type)

    return list(db.scalars(stmt).all())


@router.get(
    "/{supplier_id}",
    response_model=SupplierRead,
    summary="Obtener un proveedor por ID",
)
def get_supplier(
    supplier_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
    return supplier


# =============================================================================
# SUPPLIER PRODUCTS
# =============================================================================


@router.get(
    "/products/all",
    response_model=list[SupplierProductRead],
    summary="Listar relaciones proveedor × producto",
)
def list_supplier_products(
    db: Session = Depends(get_db),
    supplier_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    priority: int | None = Query(default=None, ge=1, le=3),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SupplierProduct]:
    stmt = select(SupplierProduct)

    if supplier_id is not None:
        stmt = stmt.where(SupplierProduct.supplier_id == supplier_id)
    if product_id is not None:
        stmt = stmt.where(SupplierProduct.product_id == product_id)
    if priority is not None:
        stmt = stmt.where(SupplierProduct.priority == priority)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# PURCHASE ORDERS
# =============================================================================


@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderRead],
    summary="Listar purchase orders",
)
def list_purchase_orders(
    db: Session = Depends(get_db),
    supplier_id: uuid.UUID | None = Query(default=None),
    destination_location_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PurchaseOrder]:
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc())

    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    if destination_location_id is not None:
        stmt = stmt.where(
            PurchaseOrder.destination_location_id == destination_location_id
        )
    if status_filter is not None:
        stmt = stmt.where(PurchaseOrder.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/purchase-orders/{po_id}",
    response_model=PurchaseOrderReadWithItems,
    summary="Obtener una PO con sus items",
)
def get_purchase_order(
    po_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PurchaseOrder:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PurchaseOrder not found",
        )
    return po


# =============================================================================
# PURCHASE ORDER ITEMS
# =============================================================================


@router.get(
    "/purchase-order-items",
    response_model=list[PurchaseOrderItemRead],
    summary="Listar items de purchase orders",
)
def list_purchase_order_items(
    db: Session = Depends(get_db),
    purchase_order_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PurchaseOrderItem]:
    stmt = select(PurchaseOrderItem)

    if purchase_order_id is not None:
        stmt = stmt.where(PurchaseOrderItem.purchase_order_id == purchase_order_id)
    if product_id is not None:
        stmt = stmt.where(PurchaseOrderItem.product_id == product_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())