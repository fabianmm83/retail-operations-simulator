"""Schemas Pydantic para el motor de simulación (M7)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    SimulationEventScope,
    SimulationEventStatus,
    SimulationEventTrigger,
    SimulationEventType,
    SimulationRunStatus,
    SimulationScenario,
)


# =============================================================================
# SIMULATION RUN
# =============================================================================


class SimulationRunBase(BaseModel):
    run_code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=200)
    description: str | None = None
    seed: int
    scenario: SimulationScenario = SimulationScenario.BASELINE
    start_date: date
    end_date: date | None = None
    current_date: date
    day_number: int = Field(default=0, ge=0)
    status: SimulationRunStatus = SimulationRunStatus.PENDING


class SimulationRunCreate(SimulationRunBase):
    config_snapshot: dict | None = None


class SimulationRunRead(SimulationRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    config_snapshot: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_tick_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# SIMULATION EVENT
# =============================================================================


class SimulationEventBase(BaseModel):
    run_id: uuid.UUID
    parent_event_id: uuid.UUID | None = None
    event_type: SimulationEventType
    scope_type: SimulationEventScope
    scope_value: str | None = Field(default=None, max_length=50)
    start_date: date
    end_date: date
    impact_factor: Decimal
    status: SimulationEventStatus = SimulationEventStatus.SCHEDULED
    trigger: SimulationEventTrigger
    metadata_json: dict | None = None


class SimulationEventCreate(SimulationEventBase):
    pass


class SimulationEventRead(SimulationEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# SIMULATION SNAPSHOT
# =============================================================================


class SimulationSnapshotBase(BaseModel):
    run_id: uuid.UUID
    day_number: int = Field(..., ge=0)
    snapshot_date: date
    data: dict


class SimulationSnapshotCreate(SimulationSnapshotBase):
    pass


class SimulationSnapshotRead(SimulationSnapshotBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# RESPUESTAS ANIDADAS
# =============================================================================


class SimulationRunReadWithEvents(SimulationRunRead):
    events: list[SimulationEventRead] = []


class SimulationRunReadWithSnapshots(SimulationRunRead):
    snapshots: list[SimulationSnapshotRead] = []