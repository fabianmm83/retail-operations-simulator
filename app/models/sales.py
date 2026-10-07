"""Modelos de ventas y logística (M6).

Define:

- Carrier      : 5 transportistas
- Order        : órdenes ONLINE + STORE
- OrderItem    : items por orden (producto + cantidad + precio congelado)
- Shipment     : envío de una orden online
- Return       : devolución de una orden entregada
- ReturnItem   : items de una devolución

Jerarquía:
    Customer 1 ── N Order 1 ── N OrderItem
    Order    1 ── N Shipment
    Order    1 ── N Return 1 ── N ReturnItem
    Carrier  1 ── N Shipment
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
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    CarrierCoverage,
    OrderChannel,
    OrderStatus,
    PaymentMethod,
    RecordStatus,
    ReturnItemCondition,
    ReturnReason,
    ReturnStatus,
    ShipmentStatus,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# CARRIER
# =============================================================================


class Carrier(UUIDMixin, TimestampMixin, Base):
    """Transportista que entrega los pedidos online.

    Cada carrier tiene una cobertura, un lead time base, un nivel de
    confiabilidad y un multiplicador de costo.
    """

    __tablename__ = "carriers"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    carrier_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="Código de negocio: CAR-01 ... CAR-05",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Parámetros operativos
    # -------------------------------------------------------------------------

    coverage: Mapped[CarrierCoverage] = mapped_column(
        SAEnum(CarrierCoverage, name="carrier_coverage", create_type=True),
        nullable=False,
    )

    base_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lead time base en días (mínimo)",
    )

    max_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lead time máximo en días",
    )

    reliability: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Confiabilidad (0.0000–1.0000)",
    )

    base_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Tarifa base en MXN",
    )

    cost_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default="1.0",
        comment="Multiplicador de costo relativo (1.0 = base)",
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
    # Relaciones ORM
    # -------------------------------------------------------------------------

    shipments: Mapped[list["Shipment"]] = relationship(
        back_populates="carrier",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "carrier_code = UPPER(carrier_code)",
            name="carriers_code_upper",
        ),
        CheckConstraint(
            "base_lead_time_days > 0",
            name="carriers_base_lead_time_positive",
        ),
        CheckConstraint(
            "max_lead_time_days >= base_lead_time_days",
            name="carriers_max_lead_gte_base",
        ),
        CheckConstraint(
            "reliability >= 0.5 AND reliability <= 1.0",
            name="carriers_reliability_range",
        ),
        CheckConstraint(
            "base_cost >= 0",
            name="carriers_base_cost_nonnegative",
        ),
        CheckConstraint(
            "cost_multiplier > 0",
            name="carriers_cost_multiplier_positive",
        ),
        Index("ix_carriers_coverage", "coverage"),
        Index("ix_carriers_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Carrier {self.carrier_code} ({self.coverage})>"


# =============================================================================
# ORDER
# =============================================================================


class Order(UUIDMixin, TimestampMixin, Base):
    """Orden de compra de un cliente.

    Puede ser ONLINE (con shipment) o STORE (venta inmediata).
    """

    __tablename__ = "orders"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    order_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de negocio: ORD-2026-000001",
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Estado del cliente al momento de la orden",
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Ubicación que surte la orden (CEDIS o tienda)",
    )

    # -------------------------------------------------------------------------
    # Estado y fechas
    # -------------------------------------------------------------------------

    channel: Mapped[OrderChannel] = mapped_column(
        SAEnum(OrderChannel, name="order_channel", create_type=True),
        nullable=False,
    )

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status", create_type=True),
        nullable=False,
        server_default=OrderStatus.PENDING.value,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha simulada de la orden",
    )

    # -------------------------------------------------------------------------
    # Pago
    # -------------------------------------------------------------------------

    payment_method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method", create_type=True),
        nullable=False,
    )

    paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # -------------------------------------------------------------------------
    # Montos
    # -------------------------------------------------------------------------

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    shipping_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    customer: Mapped["Customer"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    state: Mapped["State"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    shipments: Mapped[list["Shipment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    returns: Mapped[list["Return"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "order_number = UPPER(order_number)",
            name="orders_number_upper",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND shipping_cost >= 0 AND total >= 0",
            name="orders_amounts_nonnegative",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="orders_discount_lte_subtotal",
        ),
        Index("ix_orders_customer", "customer_id"),
        Index("ix_orders_state", "state_id"),
        Index("ix_orders_location", "location_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_channel", "channel"),
        Index("ix_orders_date", "order_date"),
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_number} ({self.status})>"


# =============================================================================
# ORDER ITEM
# =============================================================================


class OrderItem(UUIDMixin, TimestampMixin, Base):
    """Línea de una orden: un SKU con cantidad y precio congelado."""

    __tablename__ = "order_items"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="SKU específico vendido",
    )

    # -------------------------------------------------------------------------
    # Cantidad y precio
    # -------------------------------------------------------------------------

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Precio al momento de la venta (congelado)",
    )

    discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        server_default="0",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="quantity × unit_price - discount",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    order: Mapped["Order"] = relationship(
        back_populates="items",
    )

    variant: Mapped["ProductVariant"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="order_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="order_items_unit_price_nonnegative",
        ),
        CheckConstraint(
            "discount >= 0",
            name="order_items_discount_nonnegative",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="order_items_subtotal_nonnegative",
        ),
        Index("ix_order_items_order", "order_id"),
        Index("ix_order_items_variant", "variant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItem order={self.order_id} "
            f"variant={self.variant_id} qty={self.quantity}>"
        )


# =============================================================================
# SHIPMENT
# =============================================================================


class Shipment(UUIDMixin, TimestampMixin, Base):
    """Envío de una orden online.

    En V1, 1 orden online = 1 shipment (sin split). Puede haber
    retrasos o pérdidas.
    """

    __tablename__ = "shipments"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    shipment_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de negocio: SHP-2026-000001",
    )

    tracking_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Número de rastreo simulado",
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    carrier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carriers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    origin_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="CEDIS o tienda que despacha",
    )

    # -------------------------------------------------------------------------
    # Estado y fechas
    # -------------------------------------------------------------------------

    status: Mapped[ShipmentStatus] = mapped_column(
        SAEnum(ShipmentStatus, name="shipment_status", create_type=True),
        nullable=False,
        server_default=ShipmentStatus.PENDING.value,
    )

    shipped_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha de salida del origen",
    )

    estimated_delivery: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha estimada de entrega",
    )

    delivered_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha real de entrega",
    )

    # -------------------------------------------------------------------------
    # Costos
    # -------------------------------------------------------------------------

    shipping_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        server_default="0",
    )

    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 3),
        nullable=False,
        server_default="0",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    order: Mapped["Order"] = relationship(
        back_populates="shipments",
    )

    carrier: Mapped["Carrier"] = relationship(
        back_populates="shipments",
        lazy="joined",
    )

    origin_location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "shipment_number = UPPER(shipment_number)",
            name="shipments_number_upper",
        ),
        CheckConstraint(
            "shipped_at IS NULL OR estimated_delivery IS NULL OR estimated_delivery >= shipped_at",
            name="shipments_estimated_after_shipped",
        ),
        CheckConstraint(
            "delivered_at IS NULL OR shipped_at IS NULL OR delivered_at >= shipped_at",
            name="shipments_delivered_after_shipped",
        ),
        CheckConstraint(
            "shipping_cost >= 0",
            name="shipments_cost_nonnegative",
        ),
        CheckConstraint(
            "weight_kg >= 0",
            name="shipments_weight_nonnegative",
        ),
        Index("ix_shipments_order", "order_id"),
        Index("ix_shipments_carrier", "carrier_id"),
        Index("ix_shipments_origin", "origin_location_id"),
        Index("ix_shipments_status", "status"),
        Index("ix_shipments_shipped_at", "shipped_at"),
    )

    def __repr__(self) -> str:
        return f"<Shipment {self.shipment_number} ({self.status})>"


# =============================================================================
# RETURN
# =============================================================================


class Return(UUIDMixin, TimestampMixin, Base):
    """Devolución de una orden entregada.

    Una orden puede tener múltiples devoluciones parciales. Cada
    devolución tiene un motivo y pasa por su propio ciclo de vida.
    """

    __tablename__ = "returns"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Estado y fechas
    # -------------------------------------------------------------------------

    status: Mapped[ReturnStatus] = mapped_column(
        SAEnum(ReturnStatus, name="return_status", create_type=True),
        nullable=False,
        server_default=ReturnStatus.REQUESTED.value,
    )

    reason: Mapped[ReturnReason] = mapped_column(
        SAEnum(ReturnReason, name="return_reason", create_type=True),
        nullable=False,
    )

    return_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha en que el cliente solicita la devolución",
    )

    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha en que se recibe el producto devuelto",
    )

    refund_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha en que se procesa el reembolso",
    )

    # -------------------------------------------------------------------------
    # Montos
    # -------------------------------------------------------------------------

    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    order: Mapped["Order"] = relationship(
        back_populates="returns",
    )

    customer: Mapped["Customer"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    items: Mapped[list["ReturnItem"]] = relationship(
        back_populates="return_",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "refund_amount >= 0",
            name="returns_refund_nonnegative",
        ),
        CheckConstraint(
            "received_date IS NULL OR received_date >= return_date",
            name="returns_received_after_request",
        ),
        CheckConstraint(
            "refund_date IS NULL OR received_date IS NULL OR refund_date >= received_date",
            name="returns_refund_after_received",
        ),
        Index("ix_returns_order", "order_id"),
        Index("ix_returns_customer", "customer_id"),
        Index("ix_returns_status", "status"),
        Index("ix_returns_date", "return_date"),
    )

    def __repr__(self) -> str:
        return f"<Return order={self.order_id} ({self.status})>"


# =============================================================================
# RETURN ITEM
# =============================================================================


class ReturnItem(UUIDMixin, TimestampMixin, Base):
    """Línea de una devolución: referencia al order_item devuelto."""

    __tablename__ = "return_items"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("returns.id", ondelete="CASCADE"),
        nullable=False,
    )

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Item específico que se devuelve",
    )

    # -------------------------------------------------------------------------
    # Cantidad y condición
    # -------------------------------------------------------------------------

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    condition: Mapped[ReturnItemCondition] = mapped_column(
        SAEnum(
            ReturnItemCondition,
            name="return_item_condition",
            create_type=True,
        ),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    return_: Mapped["Return"] = relationship(
        back_populates="items",
    )

    order_item: Mapped["OrderItem"] = relationship(
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="return_items_quantity_positive",
        ),
        Index("ix_return_items_return", "return_id"),
        Index("ix_return_items_order_item", "order_item_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReturnItem return={self.return_id} "
            f"order_item={self.order_item_id} qty={self.quantity}>"
        )