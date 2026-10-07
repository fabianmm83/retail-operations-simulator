"""Modelos de catálogo (M1).

Define las entidades del catálogo de Cuidado con Rikochet:

- Category       : 12 categorías organizadas en 4 departamentos
- Product        : 30 productos (style codes) con precio, costo, demanda
- ProductVariant : ~250 SKUs (combinación talla × color)

Jerarquía:
    Category 1 ── N Product 1 ── N ProductVariant
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# CATEGORY
# =============================================================================


class Category(UUIDMixin, TimestampMixin, Base):
    """Categoría del catálogo (12 en total en V1).

    Cada categoría pertenece a un departamento y tiene un patrón
    estacional asignado.
    """

    __tablename__ = "categories"

    # -------------------------------------------------------------------------
    # Campos
    # -------------------------------------------------------------------------

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="Código corto en mayúsculas (PLAYERAS, SUDADERAS, ...)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre legible de la categoría",
    )

    department: Mapped[DepartmentType] = mapped_column(
        SAEnum(DepartmentType, name="department_type", create_type=True),
        nullable=False,
        comment="Departamento al que pertenece",
    )

    seasonality: Mapped[SeasonalityType] = mapped_column(
        SAEnum(SeasonalityType, name="seasonality_type", create_type=True),
        nullable=False,
        server_default=SeasonalityType.NONE.value,
        comment="Patrón estacional mensual de la categoría",
    )

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=True),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    products: Mapped[list["Product"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "code = UPPER(code)",
            name="categories_code_upper",
        ),
        Index("ix_categories_department", "department"),
        Index("ix_categories_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Category {self.code} ({self.department})>"


# =============================================================================
# PRODUCT
# =============================================================================


class Product(UUIDMixin, TimestampMixin, Base):
    """Producto del catálogo (30 en total en V1).

    Un producto es un "style" o modelo. Sus variantes (SKUs) viven en
    ProductVariant. El precio y costo viven aquí, no en la variante.
    """

    __tablename__ = "products"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    style_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de estilo: {CAT}-{SEG}-{NNNN}",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nombre comercial del producto",
    )

    # -------------------------------------------------------------------------
    # Clasificación
    # -------------------------------------------------------------------------

    segment: Mapped[SegmentType] = mapped_column(
        SAEnum(SegmentType, name="segment_type", create_type=True),
        nullable=False,
        comment="Segmento demográfico del producto",
    )

    age_group: Mapped[AgeGroupType] = mapped_column(
        SAEnum(AgeGroupType, name="age_group_type", create_type=True),
        nullable=False,
        comment="Grupo de edad objetivo",
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    sport: Mapped[SportType] = mapped_column(
        SAEnum(SportType, name="sport_type", create_type=True),
        nullable=False,
        server_default=SportType.GENERAL.value,
        comment="Deporte principal",
    )

    branded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Lleva la cara de Rikochet (producto estrella)",
    )

    # -------------------------------------------------------------------------
    # Precio y costo
    # -------------------------------------------------------------------------

    base_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Precio de lista en MXN, terminado en .99",
    )

    base_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Costo de referencia en MXN (no el de compra real)",
    )

    # -------------------------------------------------------------------------
    # Comportamiento
    # -------------------------------------------------------------------------

    demand_profile: Mapped[DemandProfileType] = mapped_column(
        SAEnum(DemandProfileType, name="demand_profile_type", create_type=True),
        nullable=False,
        comment="Perfil de demanda (HIGH, MEDIUM, LOW, NICHE)",
    )

    lifecycle_stage: Mapped[LifecycleStageType] = mapped_column(
        SAEnum(LifecycleStageType, name="lifecycle_stage_type", create_type=True),
        nullable=False,
        server_default=LifecycleStageType.MATURE.value,
        comment="Etapa actual del ciclo de vida",
    )

    launch_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha simulada de lanzamiento",
    )

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=False),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    category: Mapped["Category"] = relationship(
        back_populates="products",
        lazy="joined",
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "base_price > 0",
            name="products_price_positive",
        ),
        CheckConstraint(
            "base_cost > 0",
            name="products_cost_positive",
        ),
        CheckConstraint(
            "base_price > base_cost",
            name="products_margin_positive",
        ),
        CheckConstraint(
            "style_code = UPPER(style_code)",
            name="products_style_upper",
        ),
        CheckConstraint(
            "(segment = 'KIDS'   AND age_group = 'KIDS')  OR "
            "(segment = 'WOMEN'  AND age_group = 'ADULT') OR "
            "(segment = 'MEN'    AND age_group = 'ADULT') OR "
            "(segment = 'UNISEX' AND age_group IN ('ADULT', 'KIDS'))",
            name="products_age_group_coherent",
        ),
        Index("ix_products_category", "category_id"),
        Index("ix_products_segment", "segment"),
        Index("ix_products_demand", "demand_profile"),
        Index("ix_products_lifecycle", "lifecycle_stage"),
        Index("ix_products_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Product {self.style_code} ({self.segment})>"


# =============================================================================
# PRODUCT VARIANT (SKU)
# =============================================================================


class ProductVariant(UUIDMixin, TimestampMixin, Base):
    """Variante concreta de un producto (SKU).

    Un SKU es la combinación única de producto + talla + color.
    Aquí vive el inventario, las ventas y los movimientos.
    """

    __tablename__ = "product_variants"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Código SKU: {style_code}-{size}-{color}",
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Atributos de la variante
    # -------------------------------------------------------------------------

    size: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Talla: XS–XXL, 4–14 (kids), 24–30 (tenis), OS, etc.",
    )

    color: Mapped[ColorCode] = mapped_column(
        SAEnum(ColorCode, name="color_code", create_type=True),
        nullable=False,
        comment="Color de la variante",
    )

    barcode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="EAN-13 simulado",
    )

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=False),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    product: Mapped["Product"] = relationship(
        back_populates="variants",
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "LENGTH(size) > 0",
            name="variants_size_nonempty",
        ),
        CheckConstraint(
            "sku = UPPER(sku)",
            name="variants_sku_upper",
        ),
        UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="variants_sku_unique_per_product",
        ),
        Index("ix_variants_product", "product_id"),
        Index("ix_variants_color", "color"),
        Index("ix_variants_size", "size"),
        Index("ix_variants_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ProductVariant {self.sku}>"