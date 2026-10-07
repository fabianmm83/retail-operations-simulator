"""Motor de reabastecimiento.

Responsabilidades:

1. Evaluar reorder point en cada SKU × CEDIS → crear PurchaseOrders.
2. Evaluar reorder point en cada SKU × tienda → crear Transfers desde
   el CEDIS de la región.
3. Seleccionar proveedor según prioridad y eventos activos
   (SUPPLIER_DELAY, SUPPLIER_OUTAGE).
4. Calcular cantidades a pedir con MOQ y múltiplos de 10.
5. Construir los objetos ORM PurchaseOrder, PurchaseOrderItem,
   Transfer, TransferItem.

Las POs se agrupan por proveedor. Las transferencias son siempre
CEDIS → tienda en V1.

Este módulo NO escribe a la DB. Devuelve objetos ORM listos para
que el engine los persista.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.core.enums import (
    LocationType,
    PurchaseOrderStatus,
    TransferStatus,
)
from app.models.geography import Location, State
from app.models.inventory import Inventory
from app.models.suppliers import PurchaseOrder, PurchaseOrderItem, SupplierProduct
from app.models.inventory import Transfer, TransferItem


# =============================================================================
# CONSTANTES
# =============================================================================


# Lead time promedio para CEDIS → tienda según distancia.
DEFAULT_TRANSFER_LEAD_TIME_DAYS = 2

# Envío nacional / importado (% sobre subtotal).
SHIPPING_COST_PCT_NATIONAL = Decimal("0.03")
SHIPPING_COST_PCT_IMPORTED = Decimal("0.08")

# Redondeo de cantidades a múltiplos de N.
QUANTITY_ROUNDING = 10


# =============================================================================
# ESTRUCTURAS
# =============================================================================


@dataclass
class ReplenishmentResult:
    """Resultado de una corrida de reabastecimiento."""

    purchase_orders: list[PurchaseOrder] = field(default_factory=list)
    purchase_order_items: list[PurchaseOrderItem] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    transfer_items: list[TransferItem] = field(default_factory=list)
    supplier_skipped: list[tuple[uuid.UUID, str]] = field(default_factory=list)


# =============================================================================
# HELPERS
# =============================================================================


def _round_to_multiple(value: int, multiple: int) -> int:
    """Redondea hacia arriba al siguiente múltiplo de `multiple`."""
    if multiple <= 0:
        return value
    return ((value + multiple - 1) // multiple) * multiple


def _generate_po_number(day_number: int, sequence: int) -> str:
    year = 2026 + (day_number // 365)
    return f"PO-{year}-{sequence:06d}"


def _generate_transfer_code(day_number: int, sequence: int) -> str:
    year = 2026 + (day_number // 365)
    return f"TRF-{year}-{sequence:06d}"


# =============================================================================
# DETECCIÓN DE SKUs BAJO REORDER
# =============================================================================


def find_cedis_reorder_targets(
    inventory_rows: list[Inventory],
    location: Location,
) -> list[Inventory]:
    """Devuelve las filas de inventory de un CEDIS que están bajo reorder.

    `inventory_rows` es la lista pre-filtrada por CEDIS.
    """
    if location.location_type != LocationType.CEDIS:
        return []
    return [
        inv
        for inv in inventory_rows
        if inv.available_quantity <= inv.reorder_point
        and inv.stock_status.value in ("REORDER", "CRITICAL", "STOCKOUT")
    ]


def find_store_reorder_targets(
    inventory_rows: list[Inventory],
) -> list[Inventory]:
    """Devuelve las filas de inventory de una tienda bajo reorder."""
    return [
        inv
        for inv in inventory_rows
        if inv.available_quantity <= inv.reorder_point
        and inv.stock_status.value in ("REORDER", "CRITICAL", "STOCKOUT")
    ]


# =============================================================================
# SELECCIÓN DE PROVEEDOR
# =============================================================================


def select_supplier_for_product(
    rng: random.Random,
    supplier_products: list[SupplierProduct],
    suppliers_under_delay: set[str],
    suppliers_under_outage: set[str],
    quantity_needed: int,
) -> SupplierProduct | None:
    """Elige el SupplierProduct para un producto.

    Reglas:
    1. Filtrar suppliers inactivos.
    2. Filtrar suppliers bajo OUTAGE.
    3. Preferir prioridad 1 (no bajo DELAY).
    4. Si prioridad 1 bajo DELAY, ir a prioridad 2.
    5. Considerar importado (prioridad 3) si quantity_needed >= 500.

    Returns:
        El SupplierProduct elegido, o None si no hay ninguno disponible.
    """
    # Filtrar inactivos
    candidates = [sp for sp in supplier_products if sp.active]
    if not candidates:
        return None

    # Filtrar bajo OUTAGE
    available = [
        sp for sp in candidates
        if sp.supplier.supplier_code not in suppliers_under_outage
    ]
    if not available:
        return None

    # Preferir prioridad 1 si no está bajo DELAY
    p1_ok = [
        sp for sp in available
        if sp.priority == 1
        and sp.supplier.supplier_code not in suppliers_under_delay
    ]
    if p1_ok:
        return rng.choice(p1_ok)

    # Considerar prioridad 3 (importado) si cantidad grande
    if quantity_needed >= 500:
        p3 = [sp for sp in available if sp.priority == 3]
        if p3:
            return rng.choice(p3)

    # Preferir prioridad 2
    p2 = [sp for sp in available if sp.priority == 2]
    if p2:
        return rng.choice(p2)

    # Fallback: cualquier prioridad disponible
    return rng.choice(available)


# =============================================================================
# CANTIDAD A PEDIR
# =============================================================================


def calculate_order_quantity(
    max_stock: int,
    available_quantity: int,
    moq: int,
) -> int:
    """Cantidad a pedir: max_stock - available, ajustada a MOQ y múltiplos de 10."""
    raw = max_stock - available_quantity
    if raw <= 0:
        return 0
    rounded = _round_to_multiple(raw, QUANTITY_ROUNDING)
    return max(rounded, moq)


# =============================================================================
# CREACIÓN DE PURCHASE ORDERS
# =============================================================================


@dataclass
class PendingPOLine:
    """Línea pendiente para agrupar en una PO por proveedor."""

    supplier_product: SupplierProduct
    product_id: uuid.UUID
    quantity: int
    unit_cost: Decimal


def build_purchase_orders(
    *,
    rng: random.Random,
    day_number: int,
    sim_date: date,
    po_sequence_start: int,
    lines: list[PendingPOLine],
    destination_location_id: uuid.UUID,
) -> tuple[list[PurchaseOrder], list[PurchaseOrderItem]]:
    """Agrupa las líneas por proveedor y crea una PO por cada uno.

    Returns:
        (purchase_orders, purchase_order_items)
    """
    if not lines:
        return [], []

    # Agrupar por proveedor
    by_supplier: dict[uuid.UUID, list[PendingPOLine]] = {}
    for line in lines:
        supplier_id = line.supplier_product.supplier_id
        by_supplier.setdefault(supplier_id, []).append(line)

    purchase_orders: list[PurchaseOrder] = []
    purchase_order_items: list[PurchaseOrderItem] = []

    sequence = po_sequence_start

    for supplier_id, supplier_lines in by_supplier.items():
        # Buscar el supplier para obtener su tipo (para envío)
        sample = supplier_lines[0].supplier_product
        supplier = sample.supplier

        # Subtotal
        subtotal = sum(
            (line.unit_cost * line.quantity for line in supplier_lines),
            start=Decimal("0"),
        )

        # Envío según tipo de proveedor
        is_imported = supplier.supplier_type.value == "IMPORTED"
        shipping_pct = (
            SHIPPING_COST_PCT_IMPORTED if is_imported else SHIPPING_COST_PCT_NATIONAL
        )
        shipping_cost = (subtotal * shipping_pct).quantize(Decimal("0.01"))
        total = subtotal + shipping_cost

        # Lead time esperado
        lead_time = max(
            line.supplier_product.lead_time_days for line in supplier_lines
        )
        expected_date = sim_date + timedelta(days=lead_time)

        po = PurchaseOrder(
            id=uuid.uuid4(),
            po_number=_generate_po_number(day_number, sequence),
            supplier_id=supplier_id,
            destination_location_id=destination_location_id,
            status=PurchaseOrderStatus.PENDING,
            order_date=sim_date,
            expected_date=expected_date,
            received_date=None,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=total,
            notes=None,
        )
        purchase_orders.append(po)

        for line in supplier_lines:
            item = PurchaseOrderItem(
                id=uuid.uuid4(),
                purchase_order_id=po.id,
                product_id=line.product_id,
                quantity_ordered=line.quantity,
                quantity_received=0,
                unit_cost=line.unit_cost,
                subtotal=line.unit_cost * line.quantity,
            )
            purchase_order_items.append(item)

        sequence += 1

    return purchase_orders, purchase_order_items


# =============================================================================
# CREACIÓN DE TRANSFERS
# =============================================================================


@dataclass
class PendingTransferLine:
    """Línea pendiente para una transferencia CEDIS → tienda."""

    variant_id: uuid.UUID
    quantity: int


def build_transfer(
    *,
    day_number: int,
    sim_date: date,
    transfer_sequence: int,
    origin_location_id: uuid.UUID,
    destination_location_id: uuid.UUID,
    lines: list[PendingTransferLine],
    lead_time_days: int = DEFAULT_TRANSFER_LEAD_TIME_DAYS,
) -> tuple[Transfer, list[TransferItem]]:
    """Crea una Transfer con sus TransferItems."""
    transfer = Transfer(
        id=uuid.uuid4(),
        transfer_code=_generate_transfer_code(day_number, transfer_sequence),
        origin_location_id=origin_location_id,
        destination_location_id=destination_location_id,
        status=TransferStatus.PENDING,
        requested_date=sim_date,
        shipped_date=None,
        received_date=None,
        expected_arrival_date=sim_date + timedelta(days=lead_time_days),
    )

    items: list[TransferItem] = []
    for line in lines:
        item = TransferItem(
            id=uuid.uuid4(),
            transfer_id=transfer.id,
            variant_id=line.variant_id,
            quantity_requested=line.quantity,
            quantity_shipped=0,
            quantity_received=0,
        )
        items.append(item)

    return transfer, items


# =============================================================================
# ORQUESTADOR DE REABASTECIMIENTO
# =============================================================================


def evaluate_cedis_replenishment(
    *,
    rng: random.Random,
    day_number: int,
    sim_date: date,
    cedis: Location,
    inventory_rows: list[Inventory],
    supplier_products_by_product: dict[uuid.UUID, list[SupplierProduct]],
    suppliers_under_delay: set[str],
    suppliers_under_outage: set[str],
    variant_to_product: dict[uuid.UUID, uuid.UUID],
    po_sequence_start: int,
) -> tuple[list[PurchaseOrder], list[PurchaseOrderItem], int]:
    """Evalúa un CEDIS completo y genera POs si es necesario.

    Returns:
        (purchase_orders, purchase_order_items, next_po_sequence)
    """
    targets = find_cedis_reorder_targets(inventory_rows, cedis)
    if not targets:
        return [], [], po_sequence_start

    pending_lines: list[PendingPOLine] = []

    for inv in targets:
        product_id = variant_to_product.get(inv.variant_id)
        if product_id is None:
            continue

        supplier_products = supplier_products_by_product.get(product_id, [])
        if not supplier_products:
            continue

        quantity_needed = calculate_order_quantity(
            max_stock=inv.max_stock,
            available_quantity=inv.available_quantity,
            moq=0,  # MOQ se aplica tras elegir proveedor
        )
        if quantity_needed <= 0:
            continue

        supplier_product = select_supplier_for_product(
            rng=rng,
            supplier_products=supplier_products,
            suppliers_under_delay=suppliers_under_delay,
            suppliers_under_outage=suppliers_under_outage,
            quantity_needed=quantity_needed,
        )
        if supplier_product is None:
            continue

        # Ajustar por MOQ del proveedor elegido
        final_quantity = calculate_order_quantity(
            max_stock=inv.max_stock,
            available_quantity=inv.available_quantity,
            moq=supplier_product.minimum_order_quantity,
        )
        if final_quantity <= 0:
            continue

        pending_lines.append(
            PendingPOLine(
                supplier_product=supplier_product,
                product_id=product_id,
                quantity=final_quantity,
                unit_cost=supplier_product.unit_cost,
            )
        )

    if not pending_lines:
        return [], [], po_sequence_start

    pos, po_items = build_purchase_orders(
        rng=rng,
        day_number=day_number,
        sim_date=sim_date,
        po_sequence_start=po_sequence_start,
        lines=pending_lines,
        destination_location_id=cedis.id,
    )

    next_sequence = po_sequence_start + len(pos)
    return pos, po_items, next_sequence


def evaluate_store_replenishment(
    *,
    sim_date: date,
    day_number: int,
    store: Location,
    state: State,
    store_inventory: list[Inventory],
    cedis_by_region: dict[str, Location],
    cedis_inventory_by_location: dict[uuid.UUID, dict[uuid.UUID, Inventory]],
    transfer_sequence_start: int,
) -> tuple[Transfer | None, list[TransferItem], int]:
    """Evalúa una tienda y crea una Transfer si es necesario.

    Solo se transfiere stock que ya existe disponible en el CEDIS de la región.
    """
    targets = find_store_reorder_targets(store_inventory)
    if not targets:
        return None, [], transfer_sequence_start

    cedis = cedis_by_region.get(state.region.value)
    if cedis is None:
        return None, [], transfer_sequence_start

    cedis_inv = cedis_inventory_by_location.get(cedis.id, {})

    lines: list[PendingTransferLine] = []
    for inv in targets:
        cedis_row = cedis_inv.get(inv.variant_id)
        if cedis_row is None:
            continue
        if cedis_row.available_quantity < inv.reorder_point:
            continue

        # Cuánto necesita la tienda para volver a un nivel saludable
        # Punto medio entre reorder y max_stock
        target = (inv.reorder_point + inv.max_stock) // 2
        need = max(0, target - inv.available_quantity)

        # Cuánto puede dar el CEDIS sin bajar de su propio safety_stock
        cedis_available_for_transfer = max(
            0, cedis_row.available_quantity - cedis_row.safety_stock
        )
        send = min(need, cedis_available_for_transfer)

        if send > 0:
            lines.append(
                PendingTransferLine(variant_id=inv.variant_id, quantity=send)
            )

    if not lines:
        return None, [], transfer_sequence_start

    transfer, items = build_transfer(
        day_number=day_number,
        sim_date=sim_date,
        transfer_sequence=transfer_sequence_start,
        origin_location_id=cedis.id,
        destination_location_id=store.id,
        lines=lines,
        lead_time_days=DEFAULT_TRANSFER_LEAD_TIME_DAYS,
    )

    return transfer, items, transfer_sequence_start + 1