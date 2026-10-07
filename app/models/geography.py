"""Modelos de geografía (M2).

Define:

- State                  : 10 estados de México donde opera la empresa
- Location               : 3 CEDIS + 12 tiendas físicas = 15 ubicaciones
- StateCategoryAffinity  : matriz 10 × 12 = 120 afinidades estado × categoría

Jerarquía:
    State 1 ── N Location
    State N ── N Category  (vía StateCategoryAffinity)
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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
    IncomeGroupType,
    LocationType,
    RecordStatus,
    RegionType,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# STATE
# =============================================================================


class State(UUIDMixin, TimestampMixin, Base):
    """Estado de México donde opera Cuidado con Rikochet.

    Los 10 estados tienen diferencias económicas, de penetración online,
    de crecimiento y de afinidad por categorías.
    """

    __tablename__ = "states"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        unique=True,
        comment="Código corto del estado (CDMX, NL, JAL, ...)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre completo del estado",
    )

    # -------------------------------------------------------------------------
    # Clasificación
    # -------------------------------------------------------------------------

    region: Mapped[RegionType] = mapped_column(
        SAEnum(RegionType, name="region_type", create_type=True),
        nullable=False,
        comment="Región geográfica del estado",
    )

    income_group: Mapped[IncomeGroupType] = mapped_column(
        SAEnum(IncomeGroupType, name="income_group_type", create_type=True),
        nullable=False,
        comment="Grupo de ingreso relativo (HIGH/MEDIUM/LOW)",
    )

    # -------------------------------------------------------------------------
    # Atributos económicos y de demanda
    # -------------------------------------------------------------------------

    population_share: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        nullable=False,
        comment="Share relativo de población (0.0000–1.0000)",
    )

    income_index: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Índice de ingreso relativo (1.00 = promedio)",
    )

    online_penetration: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Penetración online (0.0000–1.0000)",
    )

    regional_factor: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Factor regional de demanda (1.00 = promedio)",
    )

    growth_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Growth rate anual (0.04 = +4%)",
    )

    # -------------------------------------------------------------------------
    # Estado
    # -------------------------------------------------------------------------

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=False),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    locations: Mapped[list["Location"]] = relationship(
        back_populates="state",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    category_affinities: Mapped[list["StateCategoryAffinity"]] = relationship(
        back_populates="state",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "code = UPPER(code)",
            name="states_code_upper",
        ),
        CheckConstraint(
            "population_share >= 0 AND population_share <= 1",
            name="states_population_share_range",
        ),
        CheckConstraint(
            "online_penetration >= 0 AND online_penetration <= 1",
            name="states_online_penetration_range",
        ),
        CheckConstraint(
            "regional_factor > 0",
            name="states_regional_factor_positive",
        ),
        CheckConstraint(
            "income_index > 0",
            name="states_income_index_positive",
        ),
        Index("ix_states_region", "region"),
        Index("ix_states_income_group", "income_group"),
        Index("ix_states_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<State {self.code} ({self.region})>"


# =============================================================================
# LOCATION
# =============================================================================


class Location(UUIDMixin, TimestampMixin, Base):
    """Ubicación física: CEDIS o tienda.

    Cada ubicación pertenece a un estado. Los CEDIS abastecen a las
    tiendas de su región; las tiendas venden directamente al cliente.
    """

    __tablename__ = "locations"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de la ubicación (CEDIS-CDMX, STORE-CDMX-01, ...)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre legible de la ubicación",
    )

    # -------------------------------------------------------------------------
    # Clasificación
    # -------------------------------------------------------------------------

    location_type: Mapped[LocationType] = mapped_column(
        SAEnum(LocationType, name="location_type", create_type=True),
        nullable=False,
        comment="Tipo de ubicación: CEDIS o STORE",
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Capacidad (placeholder para V1, ajustable en el motor)
    # -------------------------------------------------------------------------

    capacity_units: Mapped[int] = mapped_column(
        nullable=False,
        server_default="0",
        comment="Capacidad máxima en unidades (0 = sin límite en V1)",
    )

    # -------------------------------------------------------------------------
    # Estado
    # -------------------------------------------------------------------------

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=False),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    state: Mapped["State"] = relationship(
        back_populates="locations",
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "code = UPPER(code)",
            name="locations_code_upper",
        ),
        CheckConstraint(
            "capacity_units >= 0",
            name="locations_capacity_nonnegative",
        ),
        Index("ix_locations_state", "state_id"),
        Index("ix_locations_type", "location_type"),
        Index("ix_locations_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Location {self.code} ({self.location_type})>"


# =============================================================================
# STATE CATEGORY AFFINITY
# =============================================================================


class StateCategoryAffinity(UUIDMixin, TimestampMixin, Base):
    """Afinidad de un estado hacia una categoría.

    Modula la probabilidad de que un cliente de ese estado compre esa
    categoría. 1.00 = neutro, >1 = preferencia, <1 = menor afinidad.
    """

    __tablename__ = "state_category_affinity"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="CASCADE"),
        nullable=False,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Factor de afinidad
    # -------------------------------------------------------------------------

    affinity_factor: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default="1.0",
        comment="Factor de afinidad (1.0 = neutro)",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    state: Mapped["State"] = relationship(
        back_populates="category_affinities",
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "affinity_factor >= 0.5 AND affinity_factor <= 1.5",
            name="affinity_factor_range",
        ),
        UniqueConstraint(
            "state_id",
            "category_id",
            name="affinity_unique_state_category",
        ),
        Index("ix_affinity_state", "state_id"),
        Index("ix_affinity_category", "category_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<StateCategoryAffinity state={self.state_id} "
            f"category={self.category_id} factor={self.affinity_factor}>"
        )