"""Schemas Pydantic para el catálogo (M1).

Tres grupos por entidad:
- Base      : campos comunes
- Create    : para insertar
- Read      : para devolver al cliente (incluye id + timestamps)

Category y Product tienen además un schema "ReadWithProducts" /
"ReadWithVariants" para respuestas anidadas cuando se necesite.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AgeGroupType,
    ColorCode,
    DemandProfileType,
    DepartmentType,
    LifecycleStageType,
    RecordStatus,
    SeasonalityType,
    SegmentType,
    SportType,
)


# =============================================================================
# CATEGORY
# =============================================================================


class CategoryBase(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    department: DepartmentType
    seasonality: SeasonalityType = SeasonalityType.NONE
    status: RecordStatus = RecordStatus.ACTIVE


class CategoryCreate(CategoryBase):
    pass


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# PRODUCT
# =============================================================================


class ProductBase(BaseModel):
    style_code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=200)
    segment: SegmentType
    age_group: AgeGroupType
    category_id: uuid.UUID
    sport: SportType = SportType.GENERAL
    branded: bool = False
    base_price: Decimal = Field(..., gt=0)
    base_cost: Decimal = Field(..., gt=0)
    demand_profile: DemandProfileType
    lifecycle_stage: LifecycleStageType = LifecycleStageType.MATURE
    launch_date: date
    status: RecordStatus = RecordStatus.ACTIVE


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProductReadWithCategory(ProductRead):
    category: CategoryRead


# =============================================================================
# PRODUCT VARIANT (SKU)
# =============================================================================


class ProductVariantBase(BaseModel):
    sku: str = Field(..., max_length=50)
    product_id: uuid.UUID
    size: str = Field(..., max_length=10)
    color: ColorCode
    barcode: str = Field(..., max_length=20)
    status: RecordStatus = RecordStatus.ACTIVE


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantRead(ProductVariantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProductReadWithVariants(ProductRead):
    variants: list[ProductVariantRead] = []