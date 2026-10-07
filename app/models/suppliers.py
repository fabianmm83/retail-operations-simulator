"""Modelos de proveedores (M5).

Define:

- Supplier             : 8 proveedores (3 grandes, 3 medianos, 2 importados)
- SupplierProduct      : relación N:M proveedor × producto con costo y lead time
- PurchaseOrder        : encabezado de orden de compra (PO)
- PurchaseOrderItem    : detalle de SKU × cantidad por PO

Jerarquía:
    Supplier 1 ── N SupplierProduct N ── 1 Product
    Supplier 1 ── N PurchaseOrder
    PurchaseOrder 1 ── N PurchaseOrderItem N ── 1 Product
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    PurchaseOrderStatus,
    RecordStatus,
    SupplierType,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# SUPPLIER
# =============================================================================


class Supplier(UUIDMixin, TimestampMixin, Base):
    """Proveedor de Cuidado con Rikochet.

    Cada proveedor tiene un tipo, un lead time promedio, un nivel de
    confiabilidad, un MOQ, un descuento por volumen y un multiplicador
    de costo que se aplica sobre el `base_cost` del producto.
    """

    __tablename__ = "suppliers"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    supplier_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="Código de negocio: SUP-N01, SUP-M01, SUP-I01",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Clasificación
    # -------------------------------------------------------------------------

    supplier_type: Mapped[SupplierType] = mapped_column(
        SAEnum(SupplierType, name="supplier_type", create_type=True),
        nullable=False,
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Estado base de operaciones del proveedor",
    )

    # -------------------------------------------------------------------------
    # Parámetros operativos
    # -------------------------------------------------------------------------

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lead time promedio en días",
    )

    reliability: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Confiabilidad (0.0000–1.0000)",
    )

    minimum_order_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="MOQ: cantidad mínima por línea de compra",
    )

    volume_discount: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default="0",
        comment="Descuento por volumen (0.05 = 5%)",
    )

    cost_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default="1.0",
        comment="Multiplicador sobre base_cost (1.0 = base)",
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

    state: Mapped["State"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    products: Mapped[list["SupplierProduct"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="supplier",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "supplier_code = UPPER(supplier_code)",
            name="suppliers_code_upper",
        ),
        CheckConstraint(
            "lead_time_days > 0",
            name="suppliers_lead_time_positive",
        ),
        CheckConstraint(
            "reliability >= 0.5 AND reliability <= 1.0",
            name="suppliers_reliability_range",
        ),
        CheckConstraint(
            "minimum_order_quantity > 0",
            name="suppliers_moq_positive",
        ),
        CheckConstraint(
            "volume_discount >= 0 AND volume_discount <= 0.5",
            name="suppliers_volume_discount_range",
        ),
        CheckConstraint(
            "cost_multiplier > 0",
            name="suppliers_cost_multiplier_positive",
        ),
        Index("ix_suppliers_type", "supplier_type"),
        Index("ix_suppliers_state", "state_id"),
        Index("ix_suppliers_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.supplier_code} ({self.supplier_type})>"


# =============================================================================
# SUPPLIER PRODUCT
# =============================================================================


class SupplierProduct(UUIDMixin, TimestampMixin, Base):
    """Relación entre un proveedor y un producto.

    Un producto puede tener 1–3 proveedores. El proveedor con
    `priority = 1` es el preferido.

    `unit_cost` se calcula al momento de crear el registro:
        unit_cost = base_cost × cost_multiplier × (1 - volume_discount)
    y se congela para que cambios futuros en multiplicadores no
    afecten históricos.
    """

    __tablename__ = "supplier_products"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Parámetros de compra
    # -------------------------------------------------------------------------

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Costo unitario congelado al momento de la asignación",
    )

    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lead time específico para este par (puede diferir del supplier)",
    )

    minimum_order_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="MOQ específico para este par",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1 = preferido, 2 = alterno, 3 = respaldo",
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    supplier: Mapped["Supplier"] = relationship(
        back_populates="products",
        lazy="joined",
    )

    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "unit_cost > 0",
            name="supplier_products_cost_positive",
        ),
        CheckConstraint(
            "lead_time_days > 0",
            name="supplier_products_lead_time_positive",
        ),
        CheckConstraint(
            "minimum_order_quantity > 0",
            name="supplier_products_moq_positive",
        ),
        CheckConstraint(
            "priority IN (1, 2, 3)",
            name="supplier_products_priority_valid",
        ),
        UniqueConstraint(
            "supplier_id",
            "product_id",
            name="supplier_products_unique_supplier_product",
        ),
        Index("ix_supplier_products_supplier", "supplier_id"),
        Index("ix_supplier_products_product", "product_id"),
        Index("ix_supplier_products_priority", "priority"),
    )

    def __repr__(self) -> str:
        return (
            f"<SupplierProduct supplier={self.supplier_id} "
            f"product={self.product_id} priority={self.priority}>"
        )


# =============================================================================
# PURCHASE ORDER
# =============================================================================


class PurchaseOrder(UUIDMixin, TimestampMixin, Base):
    """Orden de compra a un proveedor.

    Siempre tiene como destino un CEDIS, nunca una tienda.
    El ciclo de vida es:
        PENDING → CONFIRMED → IN_TRANSIT → RECEIVED
                                          ↘ PARTIAL
                                          ↘ CANCELLED
    """

    __tablename__ = "purchase_orders"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    po_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de negocio: PO-2026-000001",
    )

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    destination_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="CEDIS destino de la orden",
    )

    # -------------------------------------------------------------------------
    # Estado y fechas
    # -------------------------------------------------------------------------

    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SAEnum(PurchaseOrderStatus, name="purchase_order_status", create_type=True),
        nullable=False,
        server_default=PurchaseOrderStatus.PENDING.value,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha en que se emite la PO",
    )

    expected_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha esperada de recepción",
    )

    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha real de recepción completa o parcial",
    )

    # -------------------------------------------------------------------------
    # Montos
    # -------------------------------------------------------------------------

    subtotal: Mapped[Decimal] = mapped_column(
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
    # Notas
    # -------------------------------------------------------------------------

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    supplier: Mapped["Supplier"] = relationship(
        back_populates="purchase_orders",
        lazy="joined",
    )

    destination_location: Mapped["Location"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "po_number = UPPER(po_number)",
            name="purchase_orders_number_upper",
        ),
        CheckConstraint(
            "expected_date >= order_date",
            name="purchase_orders_expected_after_order",
        ),
        CheckConstraint(
            "received_date IS NULL OR received_date >= order_date",
            name="purchase_orders_received_after_order",
        ),
        CheckConstraint(
            "subtotal >= 0 AND shipping_cost >= 0 AND total >= 0",
            name="purchase_orders_amounts_nonnegative",
        ),
        Index("ix_purchase_orders_supplier", "supplier_id"),
        Index("ix_purchase_orders_destination", "destination_location_id"),
        Index("ix_purchase_orders_status", "status"),
        Index("ix_purchase_orders_order_date", "order_date"),
    )

    def __repr__(self) -> str:
        return f"<PurchaseOrder {self.po_number} ({self.status})>"


# =============================================================================
# PURCHASE ORDER ITEM
# =============================================================================


class PurchaseOrderItem(UUIDMixin, TimestampMixin, Base):
    """Detalle de SKU × cantidad dentro de una purchase order.

    Se registra a nivel producto (no SKU) porque las POs se hacen en
    términos de producto y el desglose por talla/color se define al
    recibir.
    """

    __tablename__ = "purchase_order_items"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Cantidades
    # -------------------------------------------------------------------------

    quantity_ordered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Cantidad solicitada al proveedor",
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Cantidad realmente recibida (puede ser < ordered)",
    )

    # -------------------------------------------------------------------------
    # Costos
    # -------------------------------------------------------------------------

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Costo unitario congelado al momento de la PO",
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="quantity_ordered × unit_cost",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        back_populates="items",
    )

    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        lazy="joined",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0",
            name="po_items_ordered_positive",
        ),
        CheckConstraint(
            "quantity_received >= 0",
            name="po_items_received_nonnegative",
        ),
        CheckConstraint(
            "quantity_received <= quantity_ordered",
            name="po_items_received_lte_ordered",
        ),
        CheckConstraint(
            "unit_cost > 0",
            name="po_items_unit_cost_positive",
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="po_items_subtotal_nonnegative",
        ),
        UniqueConstraint(
            "purchase_order_id",
            "product_id",
            name="po_items_unique_po_product",
        ),
        Index("ix_po_items_po", "purchase_order_id"),
        Index("ix_po_items_product", "product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderItem po={self.purchase_order_id} "
            f"product={self.product_id} qty={self.quantity_ordered}>"
        )