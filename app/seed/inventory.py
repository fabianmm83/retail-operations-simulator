"""Seed de inventario (M4).

Genera:
- ~2,900 filas de inventory (647 SKUs × 3 CEDIS + 80 top sellers × 12 tiendas)
- 1 InventoryMovement tipo ADJUSTMENT de apertura por cada fila

Distribución de stock inicial (Bloque D):
- CEDIS   : ~90% del stock total
- Tiendas : ~10% del stock total

Umbrales por perfil de demanda (Bloque D):
    HIGH   → reorder 50 · safety 20 · max 200
    MEDIUM → reorder 25 · safety 10 · max 100
    LOW    → reorder 10 · safety  4 · max  40
    NICHE  → reorder  5 · safety  2 · max  20

Uso:
    python -m app.seed.inventory
"""

from __future__ import annotations

import random
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    DemandProfileType,
    LocationType,
    MovementType,
    RecordStatus,
    StockStatus,
)
from app.db.session import SessionLocal
from app.models.catalog import Product, ProductVariant
from app.models.geography import Location
from app.models.inventory import Inventory, InventoryMovement


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

SIMULATION_START = date(2026, 1, 1)
STORE_SKU_COUNT = 80  # top sellers por tienda

# Umbrales por perfil de demanda
THRESHOLDS_BY_PROFILE = {
    DemandProfileType.HIGH:   {"reorder": 50, "safety": 20, "max": 200},
    DemandProfileType.MEDIUM: {"reorder": 25, "safety": 10, "max": 100},
    DemandProfileType.LOW:    {"reorder": 10, "safety":  4, "max":  40},
    DemandProfileType.NICHE:  {"reorder":  5, "safety":  2, "max":  20},
}

# Stock inicial por perfil (rango)
STOCK_RANGE_CEDIS = {
    DemandProfileType.HIGH:   (100, 200),
    DemandProfileType.MEDIUM: ( 50, 120),
    DemandProfileType.LOW:    ( 20,  50),
    DemandProfileType.NICHE:  (  8,  20),
}

STOCK_RANGE_STORE = {
    DemandProfileType.HIGH:   (15, 25),
    DemandProfileType.MEDIUM: ( 8, 15),
    DemandProfileType.LOW:    ( 4,  8),
    DemandProfileType.NICHE:  ( 0,  0),  # NICHE no vive en tienda
}


# =============================================================================
# HELPERS
# =============================================================================


def _compute_stock_status(available: int, reorder: int, safety: int) -> StockStatus:
    """Calcula el estado del stock según los umbrales."""
    if available == 0:
        return StockStatus.STOCKOUT
    if available <= safety:
        return StockStatus.CRITICAL
    if available <= reorder:
        return StockStatus.REORDER
    return StockStatus.NORMAL


def _get_thresholds(demand_profile: DemandProfileType) -> dict[str, int]:
    """Devuelve los 3 umbrales para un perfil de demanda."""
    return THRESHOLDS_BY_PROFILE[demand_profile]


def _choose_initial_stock(
    demand_profile: DemandProfileType,
    location_type: LocationType,
) -> int:
    """Genera una cantidad inicial de stock según perfil y tipo de ubicación."""
    if location_type == LocationType.CEDIS:
        low, high = STOCK_RANGE_CEDIS[demand_profile]
    else:
        low, high = STOCK_RANGE_STORE[demand_profile]
    if high == 0:
        return 0
    return random.randint(low, high)


# =============================================================================
# SEED
# =============================================================================


def seed_inventory(db: Session) -> tuple[int, int]:
    """Crea el inventario inicial + movimientos de apertura.

    Devuelve (inventory_rows_created, movements_created).
    """
    # Verificar si ya existe
    existing = db.scalar(select(func.count()).select_from(Inventory)) or 0
    if existing > 0:
        print(f"  Inventory:   {existing} rows already exist, skipping")
        return 0, 0

    # Cargar datos base
    variants = db.scalars(select(ProductVariant)).all()
    if not variants:
        raise RuntimeError("No hay variantes. Corre el seed de catálogo primero.")

    # Mapeo variant → producto → demand_profile
    products_by_id: dict[uuid.UUID, Product] = {
        p.id: p for p in db.scalars(select(Product)).all()
    }

    locations = db.scalars(select(Location)).all()
    if not locations:
        raise RuntimeError("No hay ubicaciones. Corre el seed de geografía primero.")

    cedis = [l for l in locations if l.location_type == LocationType.CEDIS]
    stores = [l for l in locations if l.location_type == LocationType.STORE]

    # Top 80 SKUs para tiendas: los de productos HIGH y MEDIUM primero
    # Ordenamos por demand_profile (HIGH > MEDIUM > LOW > NICHE) y tomamos 80
    priority_order = {
        DemandProfileType.HIGH:   0,
        DemandProfileType.MEDIUM: 1,
        DemandProfileType.LOW:    2,
        DemandProfileType.NICHE:  3,
    }
    sorted_variants = sorted(
        variants,
        key=lambda v: (
            priority_order[products_by_id[v.product_id].demand_profile],
            v.sku,
        ),
    )
    store_variants = sorted_variants[:STORE_SKU_COUNT]

    inventory_created = 0
    movements_created = 0

    # --- CEDIS -------------------------------------------------------------
    for cedis_loc in cedis:
        for variant in variants:
            product = products_by_id[variant.product_id]
            thresholds = _get_thresholds(product.demand_profile)
            stock = _choose_initial_stock(product.demand_profile, LocationType.CEDIS)

            inv = Inventory(
                id=uuid.uuid4(),
                variant_id=variant.id,
                location_id=cedis_loc.id,
                quantity=stock,
                reserved_quantity=0,
                reorder_point=thresholds["reorder"],
                safety_stock=thresholds["safety"],
                max_stock=thresholds["max"],
                stock_status=_compute_stock_status(
                    stock, thresholds["reorder"], thresholds["safety"]
                ),
                last_movement_date=SIMULATION_START,
                status=RecordStatus.ACTIVE,
            )
            db.add(inv)
            inventory_created += 1

            # Movimiento de apertura
            movement = InventoryMovement(
                id=uuid.uuid4(),
                variant_id=variant.id,
                location_id=cedis_loc.id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=stock,
                reference_type="MANUAL",
                reference_id=None,
                movement_date=SIMULATION_START,
                notes="Initial stock adjustment",
            )
            db.add(movement)
            movements_created += 1

    # --- Tiendas -----------------------------------------------------------
    for store_loc in stores:
        for variant in store_variants:
            product = products_by_id[variant.product_id]
            thresholds = _get_thresholds(product.demand_profile)
            stock = _choose_initial_stock(product.demand_profile, LocationType.STORE)

            inv = Inventory(
                id=uuid.uuid4(),
                variant_id=variant.id,
                location_id=store_loc.id,
                quantity=stock,
                reserved_quantity=0,
                reorder_point=thresholds["reorder"],
                safety_stock=thresholds["safety"],
                max_stock=thresholds["max"],
                stock_status=_compute_stock_status(
                    stock, thresholds["reorder"], thresholds["safety"]
                ),
                last_movement_date=SIMULATION_START,
                status=RecordStatus.ACTIVE,
            )
            db.add(inv)
            inventory_created += 1

            movement = InventoryMovement(
                id=uuid.uuid4(),
                variant_id=variant.id,
                location_id=store_loc.id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=stock,
                reference_type="MANUAL",
                reference_id=None,
                movement_date=SIMULATION_START,
                notes="Initial stock adjustment",
            )
            db.add(movement)
            movements_created += 1

    db.flush()
    return inventory_created, movements_created


def run() -> None:
    """Entry point del seed de inventario."""
    print("Seeding inventory...")

    with SessionLocal() as db:
        inv_count, mov_count = seed_inventory(db)
        print(f"  Inventory:   {inv_count} rows new")
        print(f"  Movements:   {mov_count} rows new (opening adjustments)")
        db.commit()

    print("Inventory seed done.")


if __name__ == "__main__":
    run()