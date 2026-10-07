"""Modelos de clientes (M3).

Define:

- Customer                    : 10,000 clientes iniciales
- CustomerCategoryPreference  : preferencias N:M cliente × categoría (2–3 por cliente)

Jerarquía:
    Customer 1 ── N CustomerCategoryPreference
    Customer N ── 1 State
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ChannelPreference,
    CustomerProfile,
    GenderType,
    PriceSensitivity,
    RecordStatus,
    SegmentType,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# CUSTOMER
# =============================================================================


class Customer(UUIDMixin, TimestampMixin, Base):
    """Cliente de Cuidado con Rikochet.

    Un cliente vive en un estado, tiene un perfil de comportamiento
    que evoluciona con sus compras, un canal preferido, y contadores
    acumulados de su actividad.
    """

    __tablename__ = "customers"

    # -------------------------------------------------------------------------
    # Identidad
    # -------------------------------------------------------------------------

    customer_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="Código de negocio: CUST-000001",
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Formato: +52XXXXXXXXXX",
    )

    birth_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    gender: Mapped[GenderType] = mapped_column(
        SAEnum(GenderType, name="gender_type", create_type=True),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Ubicación
    # -------------------------------------------------------------------------

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    postal_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Comportamiento
    # -------------------------------------------------------------------------

    profile: Mapped[CustomerProfile] = mapped_column(
        SAEnum(CustomerProfile, name="customer_profile", create_type=True),
        nullable=False,
        server_default=CustomerProfile.NEW.value,
    )

    channel_preference: Mapped[ChannelPreference] = mapped_column(
        SAEnum(ChannelPreference, name="channel_preference", create_type=True),
        nullable=False,
    )

    preferred_segment: Mapped[SegmentType] = mapped_column(
        SAEnum(SegmentType, name="segment_type", create_type=False),
        nullable=False,
    )

    price_sensitivity: Mapped[PriceSensitivity] = mapped_column(
        SAEnum(PriceSensitivity, name="price_sensitivity", create_type=True),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Fechas y contadores
    # -------------------------------------------------------------------------

    signup_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    first_order_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    last_order_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    total_orders: Mapped[int] = mapped_column(
        nullable=False,
        server_default="0",
    )

    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    total_units: Mapped[int] = mapped_column(
        nullable=False,
        server_default="0",
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

    state: Mapped["State"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    category_preferences: Mapped[list["CustomerCategoryPreference"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "customer_code = UPPER(customer_code)",
            name="customers_code_upper",
        ),
        CheckConstraint(
            "total_orders >= 0",
            name="customers_total_orders_nonnegative",
        ),
        CheckConstraint(
            "total_revenue >= 0",
            name="customers_total_revenue_nonnegative",
        ),
        CheckConstraint(
            "total_units >= 0",
            name="customers_total_units_nonnegative",
        ),
        CheckConstraint(
            "(profile = 'NEW' AND total_orders = 0) OR (profile <> 'NEW')",
            name="customers_new_profile_no_orders",
        ),
        CheckConstraint(
            "first_order_date IS NULL OR first_order_date >= signup_date",
            name="customers_first_order_after_signup",
        ),
        CheckConstraint(
            "last_order_date IS NULL OR last_order_date >= first_order_date",
            name="customers_last_order_after_first",
        ),
        Index("ix_customers_state", "state_id"),
        Index("ix_customers_profile", "profile"),
        Index("ix_customers_channel", "channel_preference"),
        Index("ix_customers_segment", "preferred_segment"),
        Index("ix_customers_price_sensitivity", "price_sensitivity"),
        Index("ix_customers_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Customer {self.customer_code} ({self.profile})>"


# =============================================================================
# CUSTOMER CATEGORY PREFERENCE
# =============================================================================


class CustomerCategoryPreference(UUIDMixin, TimestampMixin, Base):
    """Preferencia de un cliente por una categoría.

    Cada cliente tiene 2–3 preferencias. Modula la probabilidad de
    que compre productos de esa categoría.
    """

    __tablename__ = "customer_category_preference"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Factor de preferencia
    # -------------------------------------------------------------------------

    preference_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default="1.0",
        comment="Peso relativo de la preferencia (1.0 = neutro)",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    customer: Mapped["Customer"] = relationship(
        back_populates="category_preferences",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "preference_weight > 0",
            name="preference_weight_positive",
        ),
        Index("ix_customer_pref_customer", "customer_id"),
        Index("ix_customer_pref_category", "category_id"),
        Index(
            "ux_customer_pref_unique",
            "customer_id",
            "category_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerCategoryPreference customer={self.customer_id} "
            f"category={self.category_id}>"
        )