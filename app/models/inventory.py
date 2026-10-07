"""Modelos de inventario (M4).

Define:

- Inventory           : stock por SKU × ubicación (1 fila por par)
- InventoryMovement   : movimientos append-only (trazabilidad total)
- Transfer            : transferencia entre ubicaciones (encabezado)
- TransferItem        : detalle de SKU × cantidad por transferencia

Jerarquía:
    Inventory              N ── 1 ProductVariant
    Inventory              N ── 1 Location
    InventoryMovement      N ── 1 ProductVariant
    InventoryMovement      N ── 1 Location
    Transfer               1 ── N TransferItem
    TransferItem           N ── 1 ProductVariant
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    MovementType,
    RecordStatus,
    StockStatus,
    TransferStatus,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# INVENTORY
# =============================================================================


class Inventory(UUIDMixin, TimestampMixin, Base):
    """Stock actual de un SKU en una ubicación.

    Es la tabla de estado del inventario. Cada cambio en `quantity`
    debe tener un movimiento asociado en `inventory_movements`.
    `available_quantity` es una columna GENERATED para garantizar
    consistencia (siempre = quantity - reserved_quantity).
    """

    __tablename__ = "inventory"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Cantidades
    # -------------------------------------------------------------------------

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cantidad física en piso/almacén",
    )

    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cantidad comprometida a órdenes pendientes",
    )

    available_quantity: Mapped[int] = mapped_column(
        Integer,
        Computed("quantity - reserved_quantity", persisted=True),
        comment="quantity - reserved_quantity (GENERATED)",
    )

    # -------------------------------------------------------------------------
    # Umbrales (derivados del producto, ajustables por SKU × ubicación)
    # -------------------------------------------------------------------------

    reorder_point: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Umbral de reposición (avail <= rp → REORDER)",
    )

    safety_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Colchón de seguridad (avail <= ss → CRITICAL)",
    )

    max_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Tope de inventario (4× reorder point)",
    )

    # -------------------------------------------------------------------------
    # Estado derivado
    # -------------------------------------------------------------------------

    stock_status: Mapped[StockStatus] = mapped_column(
        SAEnum(StockStatus, name="stock_status", create_type=True),
        nullable=False,
        server_default=StockStatus.NORMAL.value,
        comment="Estado calculado del stock en esta ubicación",
    )

    last_movement_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha del último movimiento",
    )

    status: Mapped[RecordStatus] = mapped_column(
        SAEnum(RecordStatus, name="record_status", create_type=False),
        nullable=False,
        server_default=RecordStatus.ACTIVE.value,
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    variant: Mapped["ProductVariant"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="inventory_quantity_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="inventory_reserved_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="inventory_reserved_lte_quantity",
        ),
        CheckConstraint(
            "reorder_point >= 0",
            name="inventory_reorder_point_nonnegative",
        ),
        CheckConstraint(
            "safety_stock >= 0",
            name="inventory_safety_stock_nonnegative",
        ),
        CheckConstraint(
            "safety_stock <= reorder_point",
            name="inventory_safety_lte_reorder",
        ),
        CheckConstraint(
            "max_stock >= reorder_point",
            name="inventory_max_gte_reorder",
        ),
        UniqueConstraint(
            "variant_id",
            "location_id",
            name="inventory_unique_variant_location",
        ),
        Index("ix_inventory_variant", "variant_id"),
        Index("ix_inventory_location", "location_id"),
        Index("ix_inventory_status", "stock_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Inventory variant={self.variant_id} "
            f"location={self.location_id} qty={self.quantity}>"
        )


# =============================================================================
# INVENTORY MOVEMENT
# =============================================================================


class InventoryMovement(UUIDMixin, TimestampMixin, Base):
    """Movimiento de inventario (append-only).

    Cada cambio en `inventory.quantity` genera un registro aquí.
    Los movimientos son inmutables: no se editan ni se borran.
    """

    __tablename__ = "inventory_movements"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Movimiento
    # -------------------------------------------------------------------------

    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(MovementType, name="movement_type", create_type=True),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Delta: positivo (entrada) o negativo (salida). Nunca cero.",
    )

    # -------------------------------------------------------------------------
    # Referencia al origen del movimiento
    # -------------------------------------------------------------------------

    reference_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="ORDER · PURCHASE_ORDER · TRANSFER · EVENT · MANUAL",
    )

    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID del objeto origen (order, PO, transfer, event)",
    )

    # -------------------------------------------------------------------------
    # Fecha simulada
    # -------------------------------------------------------------------------

    movement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha simulada del movimiento",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    variant: Mapped["ProductVariant"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "quantity <> 0",
            name="inventory_movement_quantity_nonzero",
        ),
        Index("ix_movements_variant_date", "variant_id", "movement_date"),
        Index("ix_movements_location_date", "location_id", "movement_date"),
        Index("ix_movements_type", "movement_type"),
        Index("ix_movements_reference", "reference_type", "reference_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement {self.movement_type} "
            f"qty={self.quantity} variant={self.variant_id}>"
        )


# =============================================================================
# TRANSFER
# =============================================================================


class Transfer(UUIDMixin, TimestampMixin, Base):
    """Transferencia de inventario entre dos ubicaciones.

    Por defecto, origen es un CEDIS y destino es una tienda, pero
    también puede ser CEDIS→CEDIS o tienda→CEDIS.
    """

    __tablename__ = "transfers"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    transfer_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de negocio: TRF-2026-000001",
    )

    # -------------------------------------------------------------------------
    # Origen y destino
    # -------------------------------------------------------------------------

    origin_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    destination_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Estado y fechas
    # -------------------------------------------------------------------------

    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, name="transfer_status", create_type=True),
        nullable=False,
        server_default=TransferStatus.PENDING.value,
    )

    requested_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha en que se solicita la transferencia",
    )

    shipped_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha en que sale del origen",
    )

    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha en que llega al destino",
    )

    expected_arrival_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha estimada de llegada",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    origin_location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[origin_location_id],
        lazy="joined",
    )

    destination_location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[destination_location_id],
        lazy="joined",
    )

    items: Mapped[list["TransferItem"]] = relationship(
        back_populates="transfer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "transfer_code = UPPER(transfer_code)",
            name="transfers_code_upper",
        ),
        CheckConstraint(
            "origin_location_id <> destination_location_id",
            name="transfers_origin_ne_destination",
        ),
        CheckConstraint(
            "shipped_date IS NULL OR shipped_date >= requested_date",
            name="transfers_shipped_after_requested",
        ),
        CheckConstraint(
            "received_date IS NULL OR received_date >= shipped_date",
            name="transfers_received_after_shipped",
        ),
        Index("ix_transfers_origin", "origin_location_id"),
        Index("ix_transfers_destination", "destination_location_id"),
        Index("ix_transfers_status", "status"),
        Index("ix_transfers_requested_date", "requested_date"),
    )

    def __repr__(self) -> str:
        return f"<Transfer {self.transfer_code} ({self.status})>"


# =============================================================================
# TRANSFER ITEM
# =============================================================================


class TransferItem(UUIDMixin, TimestampMixin, Base):
    """Detalle de SKU × cantidad dentro de una transferencia."""

    __tablename__ = "transfer_items"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Cantidad
    # -------------------------------------------------------------------------

    quantity_requested: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_shipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cantidad realmente enviada (puede ser < requested)",
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cantidad realmente recibida (puede ser < shipped)",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    transfer: Mapped["Transfer"] = relationship(
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
            "quantity_requested > 0",
            name="transfer_items_requested_positive",
        ),
        CheckConstraint(
            "quantity_shipped >= 0",
            name="transfer_items_shipped_nonnegative",
        ),
        CheckConstraint(
            "quantity_received >= 0",
            name="transfer_items_received_nonnegative",
        ),
        CheckConstraint(
            "quantity_shipped <= quantity_requested",
            name="transfer_items_shipped_lte_requested",
        ),
        CheckConstraint(
            "quantity_received <= quantity_shipped",
            name="transfer_items_received_lte_shipped",
        ),
        UniqueConstraint(
            "transfer_id",
            "variant_id",
            name="transfer_items_unique_transfer_variant",
        ),
        Index("ix_transfer_items_transfer", "transfer_id"),
        Index("ix_transfer_items_variant", "variant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TransferItem transfer={self.transfer_id} "
            f"variant={self.variant_id} qty={self.quantity_requested}>"
        )