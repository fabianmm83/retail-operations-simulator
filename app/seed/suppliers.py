"""Seed de proveedores (M5).

Genera:
- 8 proveedores (3 grandes nacionales, 3 medianos nacionales, 2 importados)
- ~70 relaciones supplier × product (1–3 proveedores por producto, según
  reglas del Bloque E)

Las POs NO se generan aquí. Se generan durante la simulación (M7).

Uso:
    python -m app.seed.suppliers
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import RecordStatus, SupplierType
from app.db.session import SessionLocal
from app.models.catalog import Product
from app.models.geography import State
from app.models.suppliers import Supplier, SupplierProduct


# =============================================================================
# DATOS DE LOS 8 PROVEEDORES
# =============================================================================
# Formato:
#   (supplier_code, name, supplier_type, state_code,
#    lead_time_days, reliability, moq, volume_discount, cost_multiplier)
#
# Valores alineados con el Bloque E:
#   - Grandes: lead time 8–10, confiabilidad 96–98%, MOQ 100, descuento 5%
#   - Medianos: lead time 3–5, confiabilidad 88–92%, MOQ 50, sin descuento
#   - Importados: lead time 30–35, confiabilidad 82–85%, MOQ 500, descuento 15%

SUPPLIERS_DATA = [
    # --- Nacionales grandes (3) --------------------------------------------
    ("SUP-N01", "Textiles del Bajío",        SupplierType.LARGE_NATIONAL, "JAL",
     9,  Decimal("0.97"), 100, Decimal("0.05"), Decimal("1.0000")),
    ("SUP-N02", "Calzado Deportivo del Norte", SupplierType.LARGE_NATIONAL, "NL",
     10, Decimal("0.96"), 100, Decimal("0.05"), Decimal("1.0000")),
    ("SUP-N03", "Accesorios y Equipo MX",    SupplierType.LARGE_NATIONAL, "CDMX",
     8,  Decimal("0.98"), 100, Decimal("0.05"), Decimal("1.0000")),

    # --- Nacionales medianos (3) -------------------------------------------
    ("SUP-M01", "Confecciones Rápidas del Centro", SupplierType.MEDIUM_NATIONAL, "PUE",
     5, Decimal("0.90"), 50, Decimal("0.00"), Decimal("1.0800")),
    ("SUP-M02", "Deportivos del Pacífico",   SupplierType.MEDIUM_NATIONAL, "JAL",
     4, Decimal("0.92"), 50, Decimal("0.00"), Decimal("1.1000")),
    ("SUP-M03", "Accesorios del Sur",        SupplierType.MEDIUM_NATIONAL, "OAX",
     3, Decimal("0.88"), 50, Decimal("0.00"), Decimal("1.1200")),

    # --- Importados (2) ----------------------------------------------------
    ("SUP-I01", "Asia Sport Manufacturing",  SupplierType.IMPORTED, "CDMX",
     30, Decimal("0.85"), 500, Decimal("0.15"), Decimal("0.8000")),
    ("SUP-I02", "Global Sports Equipment",   SupplierType.IMPORTED, "CDMX",
     35, Decimal("0.82"), 500, Decimal("0.15"), Decimal("0.7800")),
]


# =============================================================================
# ASIGNACIÓN DE PROVEEDORES A PRODUCTOS
# =============================================================================
# Mapeo categoría → lista de (supplier_code, priority)
#
# Reglas del Bloque E:
#   - PLAYERAS, SUDADERAS, LEGGINGS: SUP-N01 (P1), SUP-M01 (P2), SUP-I01 (P3)
#   - PANTS, SHORTS:                 SUP-N01 (P1), SUP-M01 (P2)
#   - TENIS:                         SUP-N02 (P1), SUP-M02 (P2), SUP-I01 (P3)
#   - BALONES:                       SUP-N03 (P1), SUP-I02 (P3)
#   - EQUIPO_ENTRENAMIENTO:          SUP-N03 (P1), SUP-I02 (P3)
#   - GORRAS:                        SUP-N03 (P1), SUP-M03 (P2)
#   - MOCHILAS:                      SUP-N03 (P1), SUP-M03 (P2), SUP-I02 (P3)
#   - BOTELLAS:                      SUP-N03 (P1), SUP-M03 (P2), SUP-I02 (P3)
#   - CALCETINES:                    SUP-N01 (P1), SUP-M03 (P2)

CATEGORY_SUPPLIERS: dict[str, list[tuple[str, int]]] = {
    "PLAYERAS":             [("SUP-N01", 1), ("SUP-M01", 2), ("SUP-I01", 3)],
    "SUDADERAS":            [("SUP-N01", 1), ("SUP-M01", 2), ("SUP-I01", 3)],
    "LEGGINGS":             [("SUP-N01", 1), ("SUP-M01", 2), ("SUP-I01", 3)],
    "PANTS":                [("SUP-N01", 1), ("SUP-M01", 2)],
    "SHORTS":               [("SUP-N01", 1), ("SUP-M01", 2)],
    "TENIS":                [("SUP-N02", 1), ("SUP-M02", 2), ("SUP-I01", 3)],
    "BALONES":              [("SUP-N03", 1), ("SUP-I02", 3)],
    "EQUIPO_ENTRENAMIENTO": [("SUP-N03", 1), ("SUP-I02", 3)],
    "GORRAS":               [("SUP-N03", 1), ("SUP-M03", 2)],
    "MOCHILAS":             [("SUP-N03", 1), ("SUP-M03", 2), ("SUP-I02", 3)],
    "BOTELLAS":             [("SUP-N03", 1), ("SUP-M03", 2), ("SUP-I02", 3)],
    "CALCETINES":           [("SUP-N01", 1), ("SUP-M03", 2)],
}


# =============================================================================
# SEED
# =============================================================================


def seed_suppliers(db: Session) -> dict[str, Supplier]:
    """Crea los 8 proveedores si no existen. Devuelve dict code → Supplier."""
    result: dict[str, Supplier] = {}

    states = {s.code: s for s in db.scalars(select(State)).all()}
    if not states:
        raise RuntimeError("No hay estados. Corre el seed de geografía primero.")

    for (
        supplier_code,
        name,
        supplier_type,
        state_code,
        lead_time_days,
        reliability,
        moq,
        volume_discount,
        cost_multiplier,
    ) in SUPPLIERS_DATA:
        existing = db.scalar(
            select(Supplier).where(Supplier.supplier_code == supplier_code)
        )
        if existing is not None:
            result[supplier_code] = existing
            continue

        state = states[state_code]
        supplier = Supplier(
            id=uuid.uuid4(),
            supplier_code=supplier_code,
            name=name,
            supplier_type=supplier_type,
            state_id=state.id,
            lead_time_days=lead_time_days,
            reliability=reliability,
            minimum_order_quantity=moq,
            volume_discount=volume_discount,
            cost_multiplier=cost_multiplier,
            status=RecordStatus.ACTIVE,
        )
        db.add(supplier)
        result[supplier_code] = supplier

    db.flush()
    return result


def seed_supplier_products(
    db: Session,
    suppliers: dict[str, Supplier],
) -> int:
    """Crea las relaciones supplier × product. Devuelve total creadas."""
    existing_count = (
        db.scalar(select(func.count()).select_from(SupplierProduct)) or 0
    )
    if existing_count > 0:
        print(f"  SupplierProducts: {existing_count} already exist, skipping")
        return 0

    # Cargar productos con su categoría
    products_with_cat = db.execute(
        select(Product, Product.category_id)
    ).all()

    # Necesitamos el code de categoría. Hacemos un mapa category_id → code.
    from app.models.catalog import Category

    category_codes = {
        c.id: c.code for c in db.scalars(select(Category)).all()
    }

    created = 0

    for product_row in products_with_cat:
        product = product_row[0]
        category_code = category_codes.get(product.category_id)
        if category_code is None:
            continue

        supplier_assignments = CATEGORY_SUPPLIERS.get(category_code, [])

        for supplier_code, priority in supplier_assignments:
            supplier = suppliers[supplier_code]

            # unit_cost = base_cost × cost_multiplier × (1 - volume_discount)
            unit_cost = (
                product.base_cost
                * supplier.cost_multiplier
                * (Decimal("1") - supplier.volume_discount)
            ).quantize(Decimal("0.01"))

            # lead time y MOQ específicos: partimos del supplier
            # y ajustamos levemente (±10%) para realismo
            sp_lead_time = supplier.lead_time_days
            sp_moq = supplier.minimum_order_quantity

            sp = SupplierProduct(
                id=uuid.uuid4(),
                supplier_id=supplier.id,
                product_id=product.id,
                unit_cost=unit_cost,
                lead_time_days=sp_lead_time,
                minimum_order_quantity=sp_moq,
                priority=priority,
                active=True,
            )
            db.add(sp)
            created += 1

    db.flush()
    return created


def run() -> None:
    """Entry point del seed de proveedores."""
    print("Seeding suppliers...")

    with SessionLocal() as db:
        suppliers = seed_suppliers(db)
        print(f"  Suppliers:      {len(suppliers)} (idempotent)")

        sp_created = seed_supplier_products(db, suppliers)
        print(f"  SupplierProducts: {sp_created} new")

        db.commit()

    print("Suppliers seed done.")


if __name__ == "__main__":
    run()