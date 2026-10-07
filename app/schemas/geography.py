"""Schemas Pydantic para geografía (M2)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    IncomeGroupType,
    LocationType,
    RecordStatus,
    RegionType,
)


# =============================================================================
# STATE
# =============================================================================


class StateBase(BaseModel):
    code: str = Field(..., max_length=10)
    name: str = Field(..., max_length=100)
    region: RegionType
    income_group: IncomeGroupType
    population_share: Decimal = Field(..., ge=0, le=1)
    income_index: Decimal = Field(..., gt=0)
    online_penetration: Decimal = Field(..., ge=0, le=1)
    regional_factor: Decimal = Field(..., gt=0)
    growth_rate: Decimal
    status: RecordStatus = RecordStatus.ACTIVE


class StateCreate(StateBase):
    pass


class StateRead(StateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# LOCATION
# =============================================================================


class LocationBase(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=100)
    location_type: LocationType
    state_id: uuid.UUID
    capacity_units: int = Field(default=0, ge=0)
    status: RecordStatus = RecordStatus.ACTIVE


class LocationCreate(LocationBase):
    pass


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LocationReadWithState(LocationRead):
    state: StateRead


# =============================================================================
# STATE CATEGORY AFFINITY
# =============================================================================


class StateCategoryAffinityBase(BaseModel):
    state_id: uuid.UUID
    category_id: uuid.UUID
    affinity_factor: Decimal = Field(..., ge=0.5, le=1.5)


class StateCategoryAffinityCreate(StateCategoryAffinityBase):
    pass


class StateCategoryAffinityRead(StateCategoryAffinityBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime