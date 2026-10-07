"""Motor de simulación: ciclo diario de 8 fases.

Responsabilidad: hacer avanzar el tiempo simulado día a día, aplicando
las reglas de todos los bloques (A–G) y persistiendo el estado.

Una corrida = un SimulationRun. Cada día se ejecuta en una transacción
atómica. Si algo falla, se hace rollback del día completo y se marca
el run como FAILED.

Las 8 fases del día:

  1. Avance de tiempo
  2. Eventos del día
  3. Carry-over (tránsitos, POs, backorders, entregas)
  4. Generación de demanda → órdenes
  5. Procesamiento de órdenes
  6. Logística (shipments, transfers, returns)
  7. Reabastecimiento (reorder + POs + transfers)
  8. Cierre del día (transiciones, KPIs, snapshot, commit)

IMPORTANTE:
- Todas las queries que devuelvan listas iteradas por el motor deben
  tener ORDER BY explícito.
- El motor NO muta el estado del cliente (Customer). Los contadores
  agregados (total_orders, total_revenue, profile) son calculables por
  query al final del run. Esto garantiza reproducibilidad estricta: la
  segunda corrida con el mismo seed parte exactamente del mismo estado.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    CustomerProfile,
    LocationType,
    MovementType,
    OrderChannel,
    OrderStatus,
    PurchaseOrderStatus,
    RecordStatus,
    ShipmentStatus,
    SimulationEventStatus,
    SimulationEventType,
    SimulationRunStatus,
    StockStatus,
    TransferStatus,
)
from app.models.catalog import Category, Product, ProductVariant
from app.models.customers import Customer, CustomerCategoryPreference
from app.models.geography import Location, State
from app.models.inventory import (
    Inventory,
    InventoryMovement,
    Transfer,
    TransferItem,
)
from app.models.sales import Carrier, Order, OrderItem, Shipment
from app.models.simulation import (
    SimulationEvent,
    SimulationRun,
    SimulationSnapshot,
)
from app.models.suppliers import PurchaseOrder, PurchaseOrderItem, SupplierProduct
from app.simulation import demand, events, fulfillment, replenishment
from app.simulation.rng import make_daily_rng, make_rng


logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES
# =============================================================================


def _should_snapshot(day_number: int) -> bool:
    """Snapshots según el día actual (Bloque G11.3)."""
    if day_number <= 30:
        return True
    if day_number <= 180:
        return day_number % 7 == 0
    return day_number % 30 == 0


# =============================================================================
# ESTADO INTERNO DEL ENGINE
# =============================================================================


@dataclass
class DailyStats:
    """KPIs del día. Se guarda en el snapshot."""

    date: date | None = None
    day_number: int = 0
    orders_created: int = 0
    orders_delivered: int = 0
    orders_cancelled: int = 0
    units_sold: int = 0
    revenue: Decimal = Decimal("0")
    shipments_created: int = 0
    shipments_delivered: int = 0
    shipments_delayed: int = 0
    purchase_orders_created: int = 0
    transfers_created: int = 0
    events_active: int = 0
    new_customers: int = 0


@dataclass
class EngineContext:
    """Datos que no cambian durante la corrida."""

    run: SimulationRun
    seed: int

    # Catálogo
    products: list[Product] = field(default_factory=list)
    variants: list[ProductVariant] = field(default_factory=list)
    variants_by_product: dict[uuid.UUID, list[ProductVariant]] = field(default_factory=dict)
    variant_to_product: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    products_by_id: dict[uuid.UUID, Product] = field(default_factory=dict)
    categories_by_id: dict[uuid.UUID, str] = field(default_factory=dict)
    category_by_id_obj: dict[uuid.UUID, Category] = field(default_factory=dict)

    # Geografía
    states: dict[uuid.UUID, State] = field(default_factory=dict)
    locations: list[Location] = field(default_factory=list)
    locations_by_id: dict[uuid.UUID, Location] = field(default_factory=dict)
    cedis_by_region: dict[str, Location] = field(default_factory=dict)
    stores_by_state: dict[uuid.UUID, list[Location]] = field(default_factory=dict)

    # Suppliers
    supplier_products_by_product: dict[uuid.UUID, list[SupplierProduct]] = field(default_factory=dict)

    # Carriers
    carriers: list[Carrier] = field(default_factory=list)

    # Caches mutables
    last_random_event_occurrence: dict[SimulationEventType, int] = field(default_factory=dict)


# =============================================================================
# CARGA DE CONTEXTO — TODAS LAS QUERIES CON ORDER BY
# =============================================================================


def build_context(db: Session, run: SimulationRun) -> EngineContext:
    """Carga todo el contexto read-only en memoria."""
    ctx = EngineContext(run=run, seed=run.seed)

    # --- Catálogo ---------------------------------------------------------
    ctx.products = list(
        db.scalars(select(Product).order_by(Product.style_code)).all()
    )
    ctx.products_by_id = {p.id: p for p in ctx.products}

    ctx.variants = list(
        db.scalars(select(ProductVariant).order_by(ProductVariant.sku)).all()
    )
    for v in ctx.variants:
        ctx.variants_by_product.setdefault(v.product_id, []).append(v)
        ctx.variant_to_product[v.id] = v.product_id

    categories = list(
        db.scalars(select(Category).order_by(Category.code)).all()
    )
    ctx.categories_by_id = {c.id: c.code for c in categories}
    ctx.category_by_id_obj = {c.id: c for c in categories}

    # --- Geografía --------------------------------------------------------
    states = list(db.scalars(select(State).order_by(State.code)).all())
    ctx.states = {s.id: s for s in states}

    ctx.locations = list(
        db.scalars(select(Location).order_by(Location.code)).all()
    )
    ctx.locations_by_id = {loc.id: loc for loc in ctx.locations}

    for loc in ctx.locations:
        if loc.location_type == LocationType.CEDIS:
            state = ctx.states[loc.state_id]
            ctx.cedis_by_region[state.region.value] = loc
        else:
            ctx.stores_by_state.setdefault(loc.state_id, []).append(loc)

    for sid, stores in ctx.stores_by_state.items():
        stores.sort(key=lambda s: s.code)

    # --- Suppliers --------------------------------------------------------
    sps = list(
        db.scalars(
            select(SupplierProduct).order_by(
                SupplierProduct.product_id,
                SupplierProduct.priority,
                SupplierProduct.id,
            )
        ).all()
    )
    for sp in sps:
        ctx.supplier_products_by_product.setdefault(sp.product_id, []).append(sp)

    # --- Carriers ---------------------------------------------------------
    ctx.carriers = list(
        db.scalars(select(Carrier).order_by(Carrier.carrier_code)).all()
    )

    return ctx


# =============================================================================
# FASE 1 — AVANCE DE TIEMPO
# =============================================================================


def phase_1_advance_time(run: SimulationRun) -> None:
    """Avanza el día simulado en 1."""
    if run.day_number == 0:
        run.current_date = run.start_date
        run.day_number = 1
    else:
        run.current_date = run.current_date + timedelta(days=1)
        run.day_number += 1

    logger.debug("Día %d: %s", run.day_number, run.current_date)


# =============================================================================
# FASE 2 — EVENTOS DEL DÍA
# =============================================================================


def phase_2_events(
    db: Session,
    ctx: EngineContext,
) -> tuple[list[events.EventSpec], list[SimulationEvent]]:
    """Detecta y persiste los eventos activos del día."""
    run = ctx.run
    sim_date = run.current_date

    rng = make_daily_rng(ctx.seed, "events", run.day_number)

    scheduled = events.detect_scheduled_events(sim_date, rng)
    random_events = events.detect_random_events(
        sim_date=sim_date,
        day_number=run.day_number,
        rng=rng,
        last_occurrence=ctx.last_random_event_occurrence,
    )

    cascades: list[events.EventSpec] = []
    for ev in scheduled + random_events:
        cascades.extend(events.resolve_cascades(ev, sim_date, rng))

    detected = scheduled + random_events + cascades

    rows: list[SimulationEvent] = []
    for spec in detected:
        row = SimulationEvent(
            id=uuid.uuid4(),
            run_id=run.id,
            parent_event_id=None,
            event_type=spec.event_type,
            scope_type=spec.scope_type,
            scope_value=spec.scope_value,
            start_date=spec.start_date,
            end_date=spec.end_date,
            impact_factor=Decimal(str(round(spec.impact_factor, 4))),
            status=SimulationEventStatus.ACTIVE,
            trigger=spec.trigger,
            metadata_json=spec.metadata,
        )
        db.add(row)
        rows.append(row)

    db.flush()

    active_rows = list(
        db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run.id,
                SimulationEvent.status == SimulationEventStatus.ACTIVE,
                SimulationEvent.start_date <= sim_date,
                SimulationEvent.end_date >= sim_date,
            )
            .order_by(SimulationEvent.id)
        ).all()
    )

    expired = list(
        db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run.id,
                SimulationEvent.status == SimulationEventStatus.ACTIVE,
                SimulationEvent.end_date < sim_date,
            )
            .order_by(SimulationEvent.id)
        ).all()
    )
    for ev in expired:
        ev.status = SimulationEventStatus.FINISHED

    specs = [
        events.EventSpec(
            event_type=row.event_type,
            trigger=row.trigger,
            start_date=row.start_date,
            end_date=row.end_date,
            scope_type=row.scope_type,
            scope_value=row.scope_value,
            impact_factor=float(row.impact_factor),
            metadata=row.metadata_json or {},
        )
        for row in active_rows
    ]

    return specs, rows


# =============================================================================
# FASE 3 — CARRY-OVER
# =============================================================================


def phase_3_carry_over(
    db: Session,
    ctx: EngineContext,
    stats: DailyStats,
) -> None:
    """Procesa todo lo que viene de días anteriores."""
    run = ctx.run
    sim_date = run.current_date

    # ---- POs: PENDING → CONFIRMED ----
    pending_pos = list(
        db.scalars(
            select(PurchaseOrder)
            .where(PurchaseOrder.status == PurchaseOrderStatus.PENDING)
            .order_by(PurchaseOrder.po_number)
        ).all()
    )
    for po in pending_pos:
        if po.order_date < sim_date:
            po.status = PurchaseOrderStatus.CONFIRMED

    # ---- POs: CONFIRMED → IN_TRANSIT ----
    confirmed_pos = list(
        db.scalars(
            select(PurchaseOrder)
            .where(PurchaseOrder.status == PurchaseOrderStatus.CONFIRMED)
            .order_by(PurchaseOrder.po_number)
        ).all()
    )
    for po in confirmed_pos:
        po.status = PurchaseOrderStatus.IN_TRANSIT

    # ---- POs: IN_TRANSIT → RECEIVED ----
    in_transit_pos = list(
        db.scalars(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.status == PurchaseOrderStatus.IN_TRANSIT,
                PurchaseOrder.expected_date <= sim_date,
            )
            .order_by(PurchaseOrder.po_number)
        ).all()
    )

    rng = make_daily_rng(ctx.seed, "po_receive", run.day_number)

    for po in in_transit_pos:
        supplier = po.supplier
        reliability = float(supplier.reliability)

        if rng.random() > reliability:
            po.expected_date = po.expected_date + timedelta(
                days=rng.randint(2, 5)
            )
            continue

        po.status = PurchaseOrderStatus.RECEIVED
        po.received_date = sim_date

        for item in po.items:
            item.quantity_received = item.quantity_ordered
            _apply_stock_increase(
                db=db,
                location_id=po.destination_location_id,
                product_id=item.product_id,
                quantity=item.quantity_ordered,
                movement_type=MovementType.PURCHASE_RECEIPT,
                reference_type="PURCHASE_ORDER",
                reference_id=po.id,
                movement_date=sim_date,
                ctx=ctx,
            )

    # ---- Transfers IN_TRANSIT → RECEIVED ----
    in_transit_transfers = list(
        db.scalars(
            select(Transfer)
            .where(
                Transfer.status == TransferStatus.IN_TRANSIT,
                Transfer.expected_arrival_date <= sim_date,
            )
            .order_by(Transfer.transfer_code)
        ).all()
    )
    for tr in in_transit_transfers:
        tr.status = TransferStatus.RECEIVED
        tr.received_date = sim_date
        for item in tr.items:
            item.quantity_received = item.quantity_shipped
            _apply_stock_increase(
                db=db,
                location_id=tr.destination_location_id,
                variant_id=item.variant_id,
                quantity=item.quantity_shipped,
                movement_type=MovementType.TRANSFER_IN,
                reference_type="TRANSFER",
                reference_id=tr.id,
                movement_date=sim_date,
                ctx=ctx,
            )

    # ---- Shipments en tránsito → DELIVERED / DELAYED ----
    in_transit_shipments = list(
        db.scalars(
            select(Shipment)
            .where(
                Shipment.status.in_(
                    [
                        ShipmentStatus.SHIPPED,
                        ShipmentStatus.IN_TRANSIT,
                        ShipmentStatus.OUT_FOR_DELIVERY,
                    ]
                ),
                Shipment.estimated_delivery <= sim_date,
            )
            .order_by(Shipment.shipment_number)
        ).all()
    )

    rng_ship = make_daily_rng(ctx.seed, "ship_deliver", run.day_number)

    for sh in in_transit_shipments:
        carrier_reliability = float(sh.carrier.reliability)
        if rng_ship.random() > carrier_reliability:
            sh.status = ShipmentStatus.DELAYED
            sh.estimated_delivery = sh.estimated_delivery + timedelta(
                days=rng_ship.randint(1, 3)
            )
            stats.shipments_delayed += 1
            continue

        sh.status = ShipmentStatus.DELIVERED
        sh.delivered_at = sim_date
        stats.shipments_delivered += 1

        order = sh.order
        if order.status not in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
            order.status = OrderStatus.DELIVERED
            stats.orders_delivered += 1


# =============================================================================
# HELPERS DE INVENTARIO
# =============================================================================


def _apply_stock_increase(
    *,
    db: Session,
    location_id: uuid.UUID,
    quantity: int,
    movement_type: MovementType,
    reference_type: str,
    reference_id: uuid.UUID,
    movement_date: date,
    ctx: EngineContext,
    product_id: uuid.UUID | None = None,
    variant_id: uuid.UUID | None = None,
) -> None:
    """Aumenta stock + registra movimiento."""
    if variant_id is not None:
        _apply_stock_increase_single(
            db, location_id, variant_id, quantity,
            movement_type, reference_type, reference_id, movement_date,
        )
        return

    if product_id is None:
        return

    variants = ctx.variants_by_product.get(product_id, [])
    if not variants:
        return

    sorted_variants = sorted(variants, key=lambda v: v.sku)

    per_variant = quantity // len(sorted_variants)
    remainder = quantity % len(sorted_variants)

    for i, variant in enumerate(sorted_variants):
        qty = per_variant + (1 if i < remainder else 0)
        if qty <= 0:
            continue
        _apply_stock_increase_single(
            db, location_id, variant.id, qty,
            movement_type, reference_type, reference_id, movement_date,
        )


def _apply_stock_increase_single(
    db: Session,
    location_id: uuid.UUID,
    variant_id: uuid.UUID,
    quantity: int,
    movement_type: MovementType,
    reference_type: str,
    reference_id: uuid.UUID,
    movement_date: date,
) -> None:
    inv = db.scalar(
        select(Inventory).where(
            Inventory.location_id == location_id,
            Inventory.variant_id == variant_id,
        )
    )
    if inv is None:
        inv = Inventory(
            id=uuid.uuid4(),
            variant_id=variant_id,
            location_id=location_id,
            quantity=0,
            reserved_quantity=0,
            reorder_point=25,
            safety_stock=10,
            max_stock=100,
            stock_status=StockStatus.NORMAL,
        )
        db.add(inv)

    inv.quantity += quantity
    inv.last_movement_date = movement_date
    _refresh_stock_status(inv)

    mv = InventoryMovement(
        id=uuid.uuid4(),
        variant_id=variant_id,
        location_id=location_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        movement_date=movement_date,
        notes=None,
    )
    db.add(mv)


def _refresh_stock_status(inv: Inventory) -> None:
    avail = inv.quantity - inv.reserved_quantity
    if avail == 0:
        inv.stock_status = StockStatus.STOCKOUT
    elif avail <= inv.safety_stock:
        inv.stock_status = StockStatus.CRITICAL
    elif avail <= inv.reorder_point:
        inv.stock_status = StockStatus.REORDER
    else:
        inv.stock_status = StockStatus.NORMAL


# =============================================================================
# FASE 4 — GENERACIÓN DE DEMANDA
# =============================================================================


def phase_4_demand(
    db: Session,
    ctx: EngineContext,
    active_events: list[events.EventSpec],
    stats: DailyStats,
    order_sequence_start: int,
) -> tuple[list[Order], list[OrderItem], list[Shipment], int]:
    """Genera órdenes para el día."""
    run = ctx.run
    sim_date = run.current_date

    rng = make_daily_rng(ctx.seed, "orders", run.day_number)

    customers = list(
        db.scalars(
            select(Customer)
            .where(
                Customer.status == RecordStatus.ACTIVE,
                Customer.profile != CustomerProfile.NEW,
            )
            .order_by(Customer.customer_code)
        ).all()
    )

    prefs_rows = list(
        db.scalars(
            select(CustomerCategoryPreference)
            .where(
                CustomerCategoryPreference.customer_id.in_(
                    [c.id for c in customers]
                )
            )
            .order_by(
                CustomerCategoryPreference.customer_id,
                CustomerCategoryPreference.category_id,
            )
        ).all()
    )
    prefs_by_customer: dict[uuid.UUID, dict[uuid.UUID, Decimal]] = {}
    for row in prefs_rows:
        prefs_by_customer.setdefault(row.customer_id, {})[
            row.category_id
        ] = row.preference_weight

    carriers_under_delay: set[str] = set()
    for ev in active_events:
        if ev.event_type == SimulationEventType.CARRIER_DELAY and ev.scope_value:
            carriers_under_delay.add(ev.scope_value)

    orders: list[Order] = []
    items: list[OrderItem] = []
    shipments: list[Shipment] = []

    sequence = order_sequence_start

    for customer in customers:
        prob = _customer_daily_purchase_probability(customer)
        if rng.random() >= prob:
            continue

        channel = fulfillment.choose_channel(rng, customer)

        state = ctx.states.get(customer.state_id)
        if state is None:
            continue

        origin = fulfillment.pick_fulfillment_location(
            rng=rng,
            customer=customer,
            state=state,
            cedis_by_region=ctx.cedis_by_region,
            stores_by_state=ctx.stores_by_state,
            channel=channel,
        )

        num_lines = fulfillment.choose_num_lines(rng, customer)

        draft = fulfillment.build_order_draft(
            rng=rng,
            customer=customer,
            state=state,
            channel=channel,
            order_date=sim_date,
            day_number=run.day_number,
            sequence=sequence,
            products=ctx.products,
            variants_by_product=ctx.variants_by_product,
            categories_by_id=ctx.categories_by_id,
            category_preferences=prefs_by_customer.get(customer.id, {}),
            num_lines=num_lines,
            origin_location=origin,
            carriers=ctx.carriers,
            carriers_under_delay=carriers_under_delay,
        )

        if draft is None:
            continue

        db.add(draft.order)
        for item in draft.items:
            db.add(item)
        if draft.shipment is not None:
            db.add(draft.shipment)
            shipments.append(draft.shipment)

        orders.append(draft.order)
        items.extend(draft.items)
        stats.orders_created += 1
        stats.units_sold += sum(i.quantity for i in draft.items)
        stats.revenue += draft.order.total
        if draft.shipment is not None:
            stats.shipments_created += 1

        sequence += 1

    return orders, items, shipments, sequence


def _customer_daily_purchase_probability(customer: Customer) -> float:
    """Probabilidad diaria base de compra según perfil.

    Usa el `profile` del cliente tal cual está en la DB. En V1 el motor
    NO muta este campo, por lo que siempre es el valor del seed.
    """
    mapping = {
        "LOYAL":      0.045,
        "REGULAR":    0.022,
        "OCCASIONAL": 0.013,
        "ONE_TIME":   0.0025,
        "INACTIVE":   0.002,
        "NEW":        0.0,
    }
    return mapping.get(customer.profile.value, 0.005)


# =============================================================================
# FASE 5 — PROCESAMIENTO DE ÓRDENES
# =============================================================================


def phase_5_process_orders(
    db: Session,
    ctx: EngineContext,
    orders: list[Order],
    stats: DailyStats,
) -> None:
    """Reserva stock, registra SALE.

    IMPORTANTE: NO muta el estado del Customer.

    Los contadores agregados del cliente (total_orders, total_revenue,
    total_units, first_order_date, last_order_date) y la transición de
    perfil del Bloque C5 se calcularán por query al final del run (o en
    la fase 8 de cierre de mes). En V1 los dejamos fuera para garantizar
    reproducibilidad estricta: la segunda corrida con el mismo seed
    parte exactamente del mismo estado de la DB.
    """
    run = ctx.run
    sim_date = run.current_date

    rng = make_daily_rng(ctx.seed, "process_orders", run.day_number)

    cancel_bonus = 0.0
    active_events = list(
        db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run.id,
                SimulationEvent.status == SimulationEventStatus.ACTIVE,
                SimulationEvent.start_date <= sim_date,
                SimulationEvent.end_date >= sim_date,
            )
            .order_by(SimulationEvent.id)
        ).all()
    )
    for ev in active_events:
        if ev.event_type in (
            SimulationEventType.ORDER_CANCELLATION,
            SimulationEventType.PAYMENT_FAILURE,
        ):
            cancel_bonus += float(ev.impact_factor) * 0.01

    for order in orders:
        if rng.random() < (0.05 + cancel_bonus):
            order.status = OrderStatus.CANCELLED
            order.paid = False
            stats.orders_cancelled += 1
            continue

        order.status = OrderStatus.PROCESSING
        order.paid = True

        for item in order.items:
            inv = db.scalar(
                select(Inventory).where(
                    Inventory.location_id == order.location_id,
                    Inventory.variant_id == item.variant_id,
                )
            )
            if inv is None:
                continue

            can_reserve = min(item.quantity, inv.available_quantity)
            inv.reserved_quantity += can_reserve

            inv.quantity -= item.quantity
            inv.last_movement_date = sim_date
            _refresh_stock_status(inv)

            mv = InventoryMovement(
                id=uuid.uuid4(),
                variant_id=item.variant_id,
                location_id=order.location_id,
                movement_type=MovementType.SALE,
                quantity=-item.quantity,
                reference_type="ORDER",
                reference_id=order.id,
                movement_date=sim_date,
                notes=None,
            )
            db.add(mv)

        # STORE: entrega inmediata
        if order.channel == OrderChannel.STORE:
            order.status = OrderStatus.DELIVERED
            stats.orders_delivered += 1


# =============================================================================
# FASE 6 — LOGÍSTICA
# =============================================================================


def phase_6_logistics(
    db: Session,
    ctx: EngineContext,
    shipments: list[Shipment],
    stats: DailyStats,
) -> None:
    """Avanza el estado de los shipments del día a SHIPPED."""
    run = ctx.run
    sim_date = run.current_date

    for sh in shipments:
        sh.status = ShipmentStatus.SHIPPED
        sh.shipped_at = sim_date

    older = list(
        db.scalars(
            select(Shipment)
            .where(
                Shipment.status.in_(
                    [ShipmentStatus.PENDING, ShipmentStatus.PACKED]
                ),
                Shipment.shipped_at.is_(None),
            )
            .order_by(Shipment.shipment_number)
        ).all()
    )
    for sh in older:
        sh.status = ShipmentStatus.SHIPPED
        sh.shipped_at = sim_date


# =============================================================================
# FASE 7 — REABASTECIMIENTO
# =============================================================================


def phase_7_replenishment(
    db: Session,
    ctx: EngineContext,
    stats: DailyStats,
) -> None:
    """Evalúa reorder y genera POs y transfers."""
    run = ctx.run
    sim_date = run.current_date

    active_events = list(
        db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run.id,
                SimulationEvent.status == SimulationEventStatus.ACTIVE,
                SimulationEvent.start_date <= sim_date,
                SimulationEvent.end_date >= sim_date,
            )
            .order_by(SimulationEvent.id)
        ).all()
    )

    suppliers_under_delay: set[str] = set()
    suppliers_under_outage: set[str] = set()
    for ev in active_events:
        if ev.event_type == SimulationEventType.SUPPLIER_DELAY and ev.scope_value:
            suppliers_under_delay.add(ev.scope_value)
        elif ev.event_type == SimulationEventType.SUPPLIER_OUTAGE and ev.scope_value:
            suppliers_under_outage.add(ev.scope_value)

    current_po_count = db.scalar(
        select(func.count()).select_from(PurchaseOrder)
    ) or 0

    for region in sorted(ctx.cedis_by_region.keys()):
        cedis = ctx.cedis_by_region[region]
        cedis_inventory = list(
            db.scalars(
                select(Inventory)
                .where(Inventory.location_id == cedis.id)
                .order_by(Inventory.variant_id)
            ).all()
        )

        pos, po_items, next_seq = replenishment.evaluate_cedis_replenishment(
            rng=make_daily_rng(
                ctx.seed, f"replenish_{cedis.code}", run.day_number
            ),
            day_number=run.day_number,
            sim_date=sim_date,
            cedis=cedis,
            inventory_rows=cedis_inventory,
            supplier_products_by_product=ctx.supplier_products_by_product,
            suppliers_under_delay=suppliers_under_delay,
            suppliers_under_outage=suppliers_under_outage,
            variant_to_product=ctx.variant_to_product,
            po_sequence_start=current_po_count + 1,
        )

        for po in pos:
            db.add(po)
        for item in po_items:
            db.add(item)

        current_po_count += len(pos)
        stats.purchase_orders_created += len(pos)

    current_transfer_count = db.scalar(
        select(func.count()).select_from(Transfer)
    ) or 0

    cedis_inventory_by_location: dict[uuid.UUID, dict[uuid.UUID, Inventory]] = {}
    for region in sorted(ctx.cedis_by_region.keys()):
        loc = ctx.cedis_by_region[region]
        rows = db.scalars(
            select(Inventory)
            .where(Inventory.location_id == loc.id)
            .order_by(Inventory.variant_id)
        ).all()
        cedis_inventory_by_location[loc.id] = {r.variant_id: r for r in rows}

    sorted_state_ids = sorted(
        ctx.stores_by_state.keys(),
        key=lambda sid: ctx.states[sid].code,
    )

    for state_id in sorted_state_ids:
        state = ctx.states.get(state_id)
        if state is None:
            continue
        stores = ctx.stores_by_state[state_id]

        for store in stores:
            store_inventory = list(
                db.scalars(
                    select(Inventory)
                    .where(Inventory.location_id == store.id)
                    .order_by(Inventory.variant_id)
                ).all()
            )

            transfer, items, next_seq = (
                replenishment.evaluate_store_replenishment(
                    sim_date=sim_date,
                    day_number=run.day_number,
                    store=store,
                    state=state,
                    store_inventory=store_inventory,
                    cedis_by_region=ctx.cedis_by_region,
                    cedis_inventory_by_location=cedis_inventory_by_location,
                    transfer_sequence_start=current_transfer_count + 1,
                )
            )

            if transfer is not None:
                db.add(transfer)
                for item in items:
                    db.add(item)
                current_transfer_count += 1
                stats.transfers_created += 1


# =============================================================================
# FASE 8 — CIERRE DEL DÍA
# =============================================================================


def phase_8_close_day(
    db: Session,
    ctx: EngineContext,
    stats: DailyStats,
) -> None:
    """Snapshot opcional + actualización del run."""
    run = ctx.run
    sim_date = run.current_date

    stats.date = sim_date
    stats.day_number = run.day_number

    still_active = list(
        db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run.id,
                SimulationEvent.status == SimulationEventStatus.ACTIVE,
            )
            .order_by(SimulationEvent.id)
        ).all()
    )
    stats.events_active = len(
        [e for e in still_active if e.start_date <= sim_date <= e.end_date]
    )

    if _should_snapshot(run.day_number):
        snapshot_data = {
            "totals": {
                "orders_created": stats.orders_created,
                "orders_delivered": stats.orders_delivered,
                "orders_cancelled": stats.orders_cancelled,
                "units_sold": stats.units_sold,
                "revenue": str(stats.revenue),
            },
            "logistics": {
                "shipments_created": stats.shipments_created,
                "shipments_delivered": stats.shipments_delivered,
                "shipments_delayed": stats.shipments_delayed,
            },
            "procurement": {
                "purchase_orders_created": stats.purchase_orders_created,
                "transfers_created": stats.transfers_created,
            },
            "events": {
                "events_active": stats.events_active,
            },
        }
        snap = SimulationSnapshot(
            id=uuid.uuid4(),
            run_id=run.id,
            day_number=run.day_number,
            snapshot_date=sim_date,
            data=snapshot_data,
        )
        db.add(snap)

    run.last_tick_at = datetime.utcnow()


# =============================================================================
# LOOP PRINCIPAL
# =============================================================================


def run_simulation(
    db: Session,
    run: SimulationRun,
    days: int = 365,
) -> SimulationRun:
    """Ejecuta el motor día a día."""
    run.status = SimulationRunStatus.RUNNING
    run.started_at = datetime.utcnow()
    db.add(run)
    db.commit()
    db.refresh(run)

    ctx = build_context(db, run)

    logger.info("Starting simulation: %s (%d días)", run.run_code, days)

    try:
        for _ in range(days):
            stats = DailyStats()

            phase_1_advance_time(run)
            active_events, _ = phase_2_events(db, ctx)
            phase_3_carry_over(db, ctx, stats)

            current_order_count = db.scalar(
                select(func.count()).select_from(Order)
            ) or 0

            orders, items, shipments, _ = phase_4_demand(
                db, ctx, active_events, stats,
                order_sequence_start=current_order_count + 1,
            )

            phase_5_process_orders(db, ctx, orders, stats)
            phase_6_logistics(db, ctx, shipments, stats)
            phase_7_replenishment(db, ctx, stats)
            phase_8_close_day(db, ctx, stats)

            db.commit()

            if run.day_number % 30 == 0:
                logger.info(
                    "Día %d (%s) — orders=%d revenue=%s",
                    run.day_number,
                    run.current_date,
                    stats.orders_created,
                    stats.revenue,
                )

        run.status = SimulationRunStatus.COMPLETED
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.info("Simulation complete: %s", run.run_code)

    except Exception as exc:
        db.rollback()
        run.status = SimulationRunStatus.FAILED
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.exception(
            "Simulation failed at day %d: %s", run.day_number, exc
        )
        raise

    return run