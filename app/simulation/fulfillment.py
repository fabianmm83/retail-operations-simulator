"""Motor de fulfillment: de una compra simulada a una orden concreta.

Responsabilidades:

1. Generar un `order_number` único por día (ORD-2026-000001).
2. Elegir productos y SKUs de una orden según preferencias del cliente.
3. Elegir la ubicación de surtido (CEDIS o tienda).
4. Elegir carrier según región y eventos activos.
5. Calcular costos de envío (con regla de envío gratis).
6. Construir los objetos `Order`, `OrderItem`, `Shipment`.

Este módulo NO escribe a la DB. Recibe objetos ORM ya cargados y
devuelve objetos ORM listos para `db.add(...)`. El engine decide cuándo
persistir.

En V1, 1 orden = 1 shipment. Sin split.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.core.enums import (
    CarrierCoverage,
    OrderChannel,
    OrderStatus,
    PaymentMethod,
    PriceSensitivity,
    SegmentType,
    ShipmentStatus,
)
from app.models.catalog import Product, ProductVariant
from app.models.customers import Customer
from app.models.geography import Location, State
from app.models.sales import Carrier, Order, OrderItem, Shipment


# =============================================================================
# CONSTANTES
# =============================================================================


# Subtotal a partir del cual el envío es gratis para el cliente.
FREE_SHIPPING_THRESHOLD = Decimal("599.00")

# Peso por tipo de producto (kg) para cálculo de costo de envío.
WEIGHT_BY_CATEGORY = {
    "PLAYERAS":              Decimal("0.30"),
    "SUDADERAS":             Decimal("0.60"),
    "PANTS":                 Decimal("0.55"),
    "SHORTS":                Decimal("0.35"),
    "LEGGINGS":              Decimal("0.40"),
    "TENIS":                 Decimal("1.00"),
    "BALONES":               Decimal("0.45"),
    "EQUIPO_ENTRENAMIENTO":  Decimal("1.50"),
    "GORRAS":                Decimal("0.20"),
    "MOCHILAS":              Decimal("0.80"),
    "BOTELLAS":              Decimal("0.40"),
    "CALCETINES":            Decimal("0.10"),
}

# Factor región para costo de envío (a partir del nombre de la región del cliente).
REGION_COST_FACTOR = {
    "CENTRO":    1.00,
    "NORTE":     1.10,
    "OCCIDENTE": 1.05,
    "SUR":       1.20,
}

# Mapeo de región → carrier preferido (Bloque F7.2).
CARRIER_BY_REGION: dict[str, str] = {
    "CENTRO":    "CAR-03",   # Logística Centro
    "NORTE":     "CAR-02",   # Paquetería del Norte
    "OCCIDENTE": "CAR-01",   # Envíos Rápidos MX
    "SUR":       "CAR-05",   # Económico MX
}

# Método de pago por canal (aproximado).
PAYMENT_METHOD_BY_CHANNEL: dict[OrderChannel, list[tuple[PaymentMethod, float]]] = {
    OrderChannel.ONLINE: [
        (PaymentMethod.CARD,     0.60),
        (PaymentMethod.TRANSFER, 0.15),
        (PaymentMethod.OXXO,     0.15),
        (PaymentMethod.WALLET,   0.10),
    ],
    OrderChannel.STORE: [
        (PaymentMethod.CARD,  0.70),
        (PaymentMethod.CASH,  0.30),
    ],
}

# Distribución de tallas por segmento (para ponderar el SKU específico).
SIZE_WEIGHTS_BY_SEGMENT: dict[SegmentType, dict[str, float]] = {
    SegmentType.WOMEN: {"XS": 0.05, "S": 0.20, "M": 0.35, "L": 0.25, "XL": 0.15},
    SegmentType.MEN:   {"S": 0.10, "M": 0.30, "L": 0.30, "XL": 0.20, "XXL": 0.10},
    SegmentType.KIDS:  {"4": 0.10, "6": 0.15, "8": 0.20, "10": 0.25, "12": 0.20, "14": 0.10},
    SegmentType.UNISEX: {"OS": 1.00},
}


# =============================================================================
# ESTRUCTURAS
# =============================================================================


@dataclass
class OrderDraft:
    """Borrador de orden antes de persistir.

    Incluye la Order, sus OrderItems, y opcionalmente el Shipment
    (si es ONLINE).
    """

    order: Order
    items: list[OrderItem]
    shipment: Shipment | None
    origin_location_id: uuid.UUID


# =============================================================================
# HELPERS
# =============================================================================


def _weighted_choice(
    rng: random.Random,
    options: list,
    weights: list[float],
):
    return rng.choices(options, weights=weights, k=1)[0]


def _generate_order_number(day_number: int, sequence: int) -> str:
    """Genera un número de orden: ORD-YYYY-NNNNNN.

    `day_number` es el día de simulación (1–365+). `sequence` es el índice
    dentro del día. Usamos año simulado = 2026 + (day_number // 365).
    """
    year = 2026 + (day_number // 365)
    return f"ORD-{year}-{sequence:06d}"


def _generate_shipment_number(day_number: int, sequence: int) -> str:
    year = 2026 + (day_number // 365)
    return f"SHP-{year}-{sequence:06d}"


def _generate_tracking_number(rng: random.Random) -> str:
    """Número de rastreo simulado: 2 letras + 10 dígitos."""
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    digits = "".join(str(rng.randint(0, 9)) for _ in range(10))
    return f"{letters}{digits}"


def calculate_shipping_cost(
    carrier: Carrier,
    region: str,
    weight_kg: Decimal,
) -> Decimal:
    """Calcula el costo base de envío: tarifa_base × multiplicador × región.

    No incluye la regla de envío gratis (eso se decide después).
    """
    region_factor = Decimal(str(REGION_COST_FACTOR.get(region, 1.0)))
    base = carrier.base_cost * carrier.cost_multiplier * region_factor
    # El peso añade un factor 1 + (kg - 0.5) * 0.10 (limitado a [0.8, 1.8]).
    weight_factor = Decimal("1.0") + (weight_kg - Decimal("0.5")) * Decimal("0.10")
    weight_factor = max(Decimal("0.8"), min(Decimal("1.8"), weight_factor))
    return (base * weight_factor).quantize(Decimal("0.01"))


def _should_ship_free(subtotal: Decimal) -> bool:
    return subtotal >= FREE_SHIPPING_THRESHOLD


def _weight_for_category(category_code: str) -> Decimal:
    return WEIGHT_BY_CATEGORY.get(category_code, Decimal("0.50"))


# =============================================================================
# SELECCIÓN DE PRODUCTOS Y SKUs
# =============================================================================


def _product_priority_score(
    product: Product,
    category_code: str,
    customer: Customer,
    category_preferences: dict[uuid.UUID, Decimal],
    rng: random.Random,
) -> float:
    """Puntaje de afinidad de un producto para un cliente.

    Combina:
    - match de preferred_segment (WOMEN, MEN, KIDS, UNISEX)
    - preferencia del cliente por la categoría del producto
    - price_sensitivity (HIGH penaliza productos caros)
    - demand_profile (HIGH recibe un pequeño empujón)
    - branded Rikochet recibe un boost
    """
    score = 1.0

    # Segmento
    if product.segment == customer.preferred_segment:
        score *= 2.5
    elif product.segment == SegmentType.UNISEX:
        score *= 1.2
    else:
        score *= 0.4

    # Preferencia por categoría (peso 0.5–1.5 típicamente)
    pref = category_preferences.get(product.category_id)
    if pref is not None:
        score *= float(pref)
    else:
        score *= 0.6  # categorías no preferidas pesan menos

    # Sensibilidad al precio
    if customer.price_sensitivity == PriceSensitivity.HIGH:
        # penaliza productos caros
        if product.base_price > Decimal("700"):
            score *= 0.5
    elif customer.price_sensitivity == PriceSensitivity.LOW:
        # premia productos caros
        if product.base_price > Decimal("700"):
            score *= 1.5

    # Demand profile empuja
    if product.demand_profile.value == "HIGH":
        score *= 1.6
    elif product.demand_profile.value == "MEDIUM":
        score *= 1.2
    elif product.demand_profile.value == "LOW":
        score *= 0.9
    else:  # NICHE
        score *= 0.6

    # Boost Rikochet
    if product.branded:
        score *= 1.4

    return max(score, 0.01)


def choose_products_for_order(
    rng: random.Random,
    customer: Customer,
    products: list[Product],
    categories_by_id: dict[uuid.UUID, str],
    category_preferences: dict[uuid.UUID, Decimal],
    num_lines: int,
) -> list[Product]:
    """Elige `num_lines` productos distintos para una orden."""
    if not products:
        return []

    # Calcula score para cada producto
    scores = [
        _product_priority_score(
            p,
            categories_by_id.get(p.category_id, ""),
            customer,
            category_preferences,
            rng,
        )
        for p in products
    ]

    # Muestreo sin reemplazo ponderado
    picked: list[Product] = []
    indices = list(range(len(products)))
    weights = list(scores)

    for _ in range(min(num_lines, len(products))):
        if not indices:
            break
        idx = _weighted_choice(rng, indices, weights)
        pos = indices.index(idx)
        picked.append(products[idx])
        indices.pop(pos)
        weights.pop(pos)

    return picked


def choose_sku_for_product(
    rng: random.Random,
    product: Product,
    variants: list[ProductVariant],
) -> ProductVariant | None:
    """Dado un producto, elige un SKU ponderando por talla.

    Si el producto no tiene variantes, devuelve None.
    """
    if not variants:
        return None

    size_weights = SIZE_WEIGHTS_BY_SEGMENT.get(
        product.segment, {"OS": 1.0}
    )

    # Pesos por variante = peso de talla (colores neutros por ahora)
    weights: list[float] = []
    for v in variants:
        weights.append(size_weights.get(v.size, 0.5))

    return _weighted_choice(rng, variants, weights)


# =============================================================================
# SELECCIÓN DE UBICACIÓN DE SURTIDO
# =============================================================================


def pick_fulfillment_location(
    rng: random.Random,
    customer: Customer,
    state: State,
    cedis_by_region: dict[str, Location],
    stores_by_state: dict[uuid.UUID, list[Location]],
    channel: OrderChannel,
) -> Location:
    """Elige la ubicación que surte la orden.

    - STORE: la tienda del estado del cliente (si existe).
    - ONLINE: 85% CEDIS de la región, 15% tienda del estado (si existe).
    """
    if channel == OrderChannel.STORE:
        stores = stores_by_state.get(customer.state_id, [])
        if stores:
            return rng.choice(stores)
        # Sin tienda en el estado → fallback a CEDIS
        return cedis_by_region.get(state.region.value, next(iter(cedis_by_region.values())))

    # ONLINE
    if rng.random() < 0.85:
        cedis = cedis_by_region.get(state.region.value)
        if cedis is not None:
            return cedis
        return next(iter(cedis_by_region.values()))

    stores = stores_by_state.get(customer.state_id, [])
    if stores:
        return rng.choice(stores)
    cedis = cedis_by_region.get(state.region.value)
    return cedis if cedis is not None else next(iter(cedis_by_region.values()))


# =============================================================================
# SELECCIÓN DE CARRIER
# =============================================================================


def select_carrier(
    rng: random.Random,
    state: State,
    carriers: list[Carrier],
    carriers_under_delay: set[str],
) -> Carrier:
    """Elige el carrier según región, evitando los que están bajo CARRIER_DELAY."""
    preferred_code = CARRIER_BY_REGION.get(state.region.value, "CAR-01")

    available = [c for c in carriers if c.carrier_code not in carriers_under_delay]

    if not available:
        available = carriers  # fallback: no hay alternativa

    # Si el preferido está disponible, úsalo
    for c in available:
        if c.carrier_code == preferred_code:
            return c

    # Fallback: carrier de cobertura NATIONAL
    national = [c for c in available if c.coverage == CarrierCoverage.NATIONAL]
    if national:
        return rng.choice(national)

    return rng.choice(available)


# =============================================================================
# CONSTRUCCIÓN DE LA ORDEN
# =============================================================================


def build_order_draft(
    *,
    rng: random.Random,
    customer: Customer,
    state: State,
    channel: OrderChannel,
    order_date: date,
    day_number: int,
    sequence: int,
    products: list[Product],
    variants_by_product: dict[uuid.UUID, list[ProductVariant]],
    categories_by_id: dict[uuid.UUID, str],
    category_preferences: dict[uuid.UUID, Decimal],
    num_lines: int,
    origin_location: Location,
    carriers: list[Carrier] | None,
    carriers_under_delay: set[str] | None,
) -> OrderDraft | None:
    """Construye una orden completa (Order + OrderItems + Shipment).

    Returns:
        Un OrderDraft con los objetos ORM listos para `db.add(...)`,
        o None si no se pudo construir (ej. sin productos válidos).
    """
    # 1. Elegir productos
    picked_products = choose_products_for_order(
        rng=rng,
        customer=customer,
        products=products,
        categories_by_id=categories_by_id,
        category_preferences=category_preferences,
        num_lines=num_lines,
    )
    if not picked_products:
        return None

    # 2. Por cada producto, elegir SKU, cantidad y construir OrderItem
    order_id = uuid.uuid4()
    order_items: list[OrderItem] = []
    subtotal = Decimal("0")
    total_weight = Decimal("0")

    for product in picked_products:
        variants = variants_by_product.get(product.id, [])
        variant = choose_sku_for_product(rng, product, variants)
        if variant is None:
            continue

        quantity = 1
        # Básicos (calcetines) pueden llevar 2
        if categories_by_id.get(product.category_id) == "CALCETINES":
            quantity = rng.choice([1, 2, 2, 3])

        unit_price = product.base_price
        line_discount = Decimal("0")  # promociones fuera de V1
        line_subtotal = (unit_price * quantity) - line_discount

        order_item = OrderItem(
            id=uuid.uuid4(),
            order_id=order_id,
            variant_id=variant.id,
            quantity=quantity,
            unit_price=unit_price,
            discount=line_discount,
            subtotal=line_subtotal,
        )
        order_items.append(order_item)
        subtotal += line_subtotal
        total_weight += _weight_for_category(categories_by_id.get(product.category_id, ""))

    if not order_items:
        return None

    # 3. Método de pago
    pm_options = PAYMENT_METHOD_BY_CHANNEL[channel]
    payment_method = _weighted_choice(
        rng, [pm for pm, _ in pm_options], [w for _, w in pm_options]
    )

    # 4. Costo de envío (solo ONLINE)
    shipping_cost = Decimal("0")
    carrier: Carrier | None = None

    if channel == OrderChannel.ONLINE:
        carriers = carriers or []
        carriers_under_delay = carriers_under_delay or set()
        if not carriers:
            return None
        carrier = select_carrier(rng, state, carriers, carriers_under_delay)
        shipping_cost = calculate_shipping_cost(carrier, state.region.value, total_weight)
        if _should_ship_free(subtotal):
            # La empresa absorbe el costo, pero se registra en el shipment.
            pass  # el cliente no paga shipping_cost, pero el campo lo guarda igual

    # 5. Total
    discount = Decimal("0")
    total = subtotal - discount + (
        Decimal("0") if channel == OrderChannel.ONLINE and _should_ship_free(subtotal)
        else shipping_cost
    )

    # 6. Order
    order = Order(
        id=order_id,
        order_number=_generate_order_number(day_number, sequence),
        customer_id=customer.id,
        state_id=customer.state_id,
        location_id=origin_location.id,
        channel=channel,
        status=OrderStatus.CONFIRMED,
        order_date=order_date,
        payment_method=payment_method,
        paid=True,
        subtotal=subtotal,
        discount=discount,
        shipping_cost=shipping_cost,
        total=total,
    )

    # 7. Shipment (solo ONLINE)
    shipment: Shipment | None = None
    if channel == OrderChannel.ONLINE and carrier is not None:
        lead_time = rng.randint(
            carrier.base_lead_time_days,
            carrier.max_lead_time_days,
        )
        estimated = order_date + timedelta(days=lead_time)

        shipment = Shipment(
            id=uuid.uuid4(),
            shipment_number=_generate_shipment_number(day_number, sequence),
            tracking_number=_generate_tracking_number(rng),
            order_id=order_id,
            carrier_id=carrier.id,
            origin_location_id=origin_location.id,
            status=ShipmentStatus.PENDING,
            shipped_at=None,
            estimated_delivery=estimated,
            delivered_at=None,
            shipping_cost=shipping_cost,
            weight_kg=total_weight,
        )

    return OrderDraft(
        order=order,
        items=order_items,
        shipment=shipment,
        origin_location_id=origin_location.id,
    )


# =============================================================================
# HELPERS EXPUESTOS
# =============================================================================


def choose_channel(
    rng: random.Random,
    customer: Customer,
) -> OrderChannel:
    """Elige el canal de la orden según la preferencia del cliente."""
    pref = customer.channel_preference.value

    if pref == "ONLINE":
        return OrderChannel.ONLINE if rng.random() < 0.95 else OrderChannel.STORE
    if pref == "STORE":
        return OrderChannel.STORE if rng.random() < 0.90 else OrderChannel.ONLINE
    # OMNICHANNEL
    return OrderChannel.ONLINE if rng.random() < 0.60 else OrderChannel.STORE


def choose_num_lines(
    rng: random.Random,
    customer: Customer,
) -> int:
    """Número de líneas de la orden según perfil del cliente."""
    profile = customer.profile.value

    if profile in ("NEW", "ONE_TIME"):
        return rng.choice([1, 1, 2])
    if profile == "OCCASIONAL":
        return rng.choice([1, 2, 2])
    if profile == "REGULAR":
        return rng.choice([1, 2, 2, 3])
    if profile == "LOYAL":
        return rng.choice([2, 2, 3, 3, 4])
    # INACTIVE
    return rng.choice([1, 1, 2])