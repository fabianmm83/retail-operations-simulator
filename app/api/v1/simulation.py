"""Endpoints read-only de simulación (M7).

Los runs, eventos y snapshots se crean durante la ejecución del motor
de simulación. Aquí solo se consultan.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.simulation import (
    SimulationEvent,
    SimulationRun,
    SimulationSnapshot,
)
from app.schemas.simulation import (
    SimulationEventRead,
    SimulationRunRead,
    SimulationRunReadWithEvents,
    SimulationRunReadWithSnapshots,
    SimulationSnapshotRead,
)


router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


# =============================================================================
# SIMULATION RUNS
# =============================================================================


@router.get(
    "/runs",
    response_model=list[SimulationRunRead],
    summary="Listar simulaciones",
)
def list_runs(
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    scenario: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SimulationRun]:
    stmt = select(SimulationRun).order_by(SimulationRun.created_at.desc())

    if status_filter is not None:
        stmt = stmt.where(SimulationRun.status == status_filter)
    if scenario is not None:
        stmt = stmt.where(SimulationRun.scenario == scenario)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/runs/{run_id}",
    response_model=SimulationRunReadWithEvents,
    summary="Obtener una simulación con sus eventos",
)
def get_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SimulationRun:
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SimulationRun not found",
        )
    return run


@router.get(
    "/runs/{run_id}/snapshots",
    response_model=SimulationRunReadWithSnapshots,
    summary="Obtener una simulación con sus snapshots",
)
def get_run_with_snapshots(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SimulationRun:
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SimulationRun not found",
        )
    return run


# =============================================================================
# SIMULATION EVENTS
# =============================================================================


@router.get(
    "/events",
    response_model=list[SimulationEventRead],
    summary="Listar eventos de simulación",
)
def list_events(
    db: Session = Depends(get_db),
    run_id: uuid.UUID | None = Query(default=None),
    event_type: str | None = Query(default=None),
    scope_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SimulationEvent]:
    stmt = select(SimulationEvent).order_by(SimulationEvent.start_date.desc())

    if run_id is not None:
        stmt = stmt.where(SimulationEvent.run_id == run_id)
    if event_type is not None:
        stmt = stmt.where(SimulationEvent.event_type == event_type)
    if scope_type is not None:
        stmt = stmt.where(SimulationEvent.scope_type == scope_type)
    if status_filter is not None:
        stmt = stmt.where(SimulationEvent.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


# =============================================================================
# SIMULATION SNAPSHOTS
# =============================================================================


@router.get(
    "/snapshots",
    response_model=list[SimulationSnapshotRead],
    summary="Listar snapshots",
)
def list_snapshots(
    db: Session = Depends(get_db),
    run_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SimulationSnapshot]:
    stmt = select(SimulationSnapshot).order_by(
        SimulationSnapshot.day_number.desc()
    )

    if run_id is not None:
        stmt = stmt.where(SimulationSnapshot.run_id == run_id)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())