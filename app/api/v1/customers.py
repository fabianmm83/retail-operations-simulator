"""Endpoints read-only de clientes (M3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customers import Customer, CustomerCategoryPreference
from app.schemas.customers import (
    CustomerCategoryPreferenceRead,
    CustomerRead,
    CustomerReadWithPreferences,
)


router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


# =============================================================================
# CUSTOMERS
# =============================================================================


@router.get(
    "",
    response_model=list[CustomerRead],
    summary="Listar clientes",
)
def list_customers(
    db: Session = Depends(get_db),
    state_id: uuid.UUID | None = Query(default=None),
    profile: str | None = Query(default=None),
    channel_preference: str | None = Query(default=None),
    preferred_segment: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.customer_code)

    if state_id is not None:
        stmt = stmt.where(Customer.state_id == state_id)
    if profile is not None:
        stmt = stmt.where(Customer.profile == profile)
    if channel_preference is not None:
        stmt = stmt.where(Customer.channel_preference == channel_preference)
    if preferred_segment is not None:
        stmt = stmt.where(Customer.preferred_segment == preferred_segment)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/{customer_id}",
    response_model=CustomerReadWithPreferences,
    summary="Obtener un cliente con sus preferencias",
)
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return customer


# =============================================================================
# CUSTOMER CATEGORY PREFERENCE
# =============================================================================


@router.get(
    "/preferences/all",
    response_model=list[CustomerCategoryPreferenceRead],
    summary="Listar preferencias de categoría",
)
def list_preferences(
    db: Session = Depends(get_db),
    customer_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CustomerCategoryPreference]:
    stmt = select(CustomerCategoryPreference)

    if customer_id is not None:
        stmt = stmt.where(CustomerCategoryPreference.customer_id == customer_id)
    if category_id is not None:
        stmt = stmt.where(CustomerCategoryPreference.category_id == category_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())