"""Endpoints read-only de geografía (M2)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.geography import Location, State, StateCategoryAffinity
from app.schemas.geography import (
    LocationRead,
    LocationReadWithState,
    StateCategoryAffinityRead,
    StateRead,
)


router = APIRouter(prefix="/api/v1/geography", tags=["geography"])


# =============================================================================
# STATES
# =============================================================================


@router.get(
    "/states",
    response_model=list[StateRead],
    summary="Listar estados",
)
def list_states(db: Session = Depends(get_db)) -> list[State]:
    stmt = select(State).order_by(State.code)
    return list(db.scalars(stmt).all())


@router.get(
    "/states/{state_id}",
    response_model=StateRead,
    summary="Obtener un estado por ID",
)
def get_state(
    state_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> State:
    state = db.get(State, state_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="State not found",
        )
    return state


# =============================================================================
# LOCATIONS
# =============================================================================


@router.get(
    "/locations",
    response_model=list[LocationRead],
    summary="Listar ubicaciones (CEDIS + tiendas)",
)
def list_locations(
    db: Session = Depends(get_db),
    state_id: uuid.UUID | None = Query(default=None),
    location_type: str | None = Query(default=None),
) -> list[Location]:
    stmt = select(Location).order_by(Location.code)

    if state_id is not None:
        stmt = stmt.where(Location.state_id == state_id)
    if location_type is not None:
        stmt = stmt.where(Location.location_type == location_type)

    return list(db.scalars(stmt).all())


@router.get(
    "/locations/{location_id}",
    response_model=LocationReadWithState,
    summary="Obtener una ubicación con su estado",
)
def get_location(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Location:
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


# =============================================================================
# STATE CATEGORY AFFINITY
# =============================================================================


@router.get(
    "/affinities",
    response_model=list[StateCategoryAffinityRead],
    summary="Listar afinidades estado × categoría",
)
def list_affinities(
    db: Session = Depends(get_db),
    state_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
) -> list[StateCategoryAffinity]:
    stmt = select(StateCategoryAffinity)

    if state_id is not None:
        stmt = stmt.where(StateCategoryAffinity.state_id == state_id)
    if category_id is not None:
        stmt = stmt.where(StateCategoryAffinity.category_id == category_id)

    return list(db.scalars(stmt).all())