"""Seed de geografía (M2).

Genera:
- 10 estados de México
- 15 ubicaciones (3 CEDIS + 12 tiendas)
- 120 afinidades estado × categoría

Idempotente: si un estado/ubicación/afinidad ya existe, no lo duplica.

Uso:
    python -m app.seed.geography
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    IncomeGroupType,
    LocationType,
    RecordStatus,
    RegionType,
)
from app.db.session import SessionLocal
from app.models.catalog import Category
from app.models.geography import Location, State, StateCategoryAffinity


# =============================================================================
# DATOS DE LOS 10 ESTADOS
# =============================================================================
# Formato:
#   (code, name, region, income_group, population_share, income_index,
#    online_penetration, regional_factor, growth_rate)
#
# Valores alineados con Bloque B de la planeación.

STATES_DATA = [
    ("CDMX",   "Ciudad de México",   RegionType.CENTRO,    IncomeGroupType.HIGH,   Decimal("0.1300"), Decimal("1.45"), Decimal("0.7800"), Decimal("1.6200"), Decimal("0.0400")),
    ("NL",     "Nuevo León",          RegionType.NORTE,     IncomeGroupType.HIGH,   Decimal("0.0800"), Decimal("1.40"), Decimal("0.7200"), Decimal("1.2800"), Decimal("0.0600")),
    ("JAL",    "Jalisco",             RegionType.OCCIDENTE, IncomeGroupType.HIGH,   Decimal("0.1200"), Decimal("1.10"), Decimal("0.6800"), Decimal("1.2600"), Decimal("0.0500")),
    ("EDOMEX", "Estado de México",    RegionType.CENTRO,    IncomeGroupType.MEDIUM, Decimal("0.1800"), Decimal("0.95"), Decimal("0.6500"), Decimal("1.1800"), Decimal("0.0700")),
    ("QRO",    "Querétaro",           RegionType.CENTRO,    IncomeGroupType.MEDIUM, Decimal("0.0400"), Decimal("1.15"), Decimal("0.7000"), Decimal("0.9400"), Decimal("0.0800")),
    ("PUE",    "Puebla",              RegionType.CENTRO,    IncomeGroupType.MEDIUM, Decimal("0.0900"), Decimal("0.85"), Decimal("0.5800"), Decimal("0.8600"), Decimal("0.0300")),
    ("BC",     "Baja California",     RegionType.NORTE,     IncomeGroupType.MEDIUM, Decimal("0.0500"), Decimal("1.05"), Decimal("0.6600"), Decimal("0.8200"), Decimal("0.0500")),
    ("OAX",    "Oaxaca",              RegionType.SUR,       IncomeGroupType.LOW,    Decimal("0.0600"), Decimal("0.65"), Decimal("0.4500"), Decimal("0.5400"), Decimal("0.0200")),
    ("CHIS",   "Chiapas",             RegionType.SUR,       IncomeGroupType.LOW,    Decimal("0.0700"), Decimal("0.60"), Decimal("0.4000"), Decimal("0.5200"), Decimal("0.0200")),
    ("GRO",    "Guerrero",            RegionType.SUR,       IncomeGroupType.LOW,    Decimal("0.0500"), Decimal("0.70"), Decimal("0.4800"), Decimal("0.4800"), Decimal("0.0100")),
]


# =============================================================================
# DATOS DE LAS 15 UBICACIONES
# =============================================================================
# Formato:
#   (code, name, location_type, state_code, capacity_units)

LOCATIONS_DATA = [
    # --- CEDIS (3) ----------------------------------------------------------
    ("CEDIS-CDMX", "CEDIS Centro (CDMX)",     LocationType.CEDIS, "CDMX", 0),
    ("CEDIS-NL",   "CEDIS Norte (NL)",        LocationType.CEDIS, "NL",   0),
    ("CEDIS-JAL",  "CEDIS Occidente (JAL)",   LocationType.CEDIS, "JAL",  0),

    # --- Tiendas CDMX (3) ---------------------------------------------------
    ("STORE-CDMX-01", "Tienda CDMX Polanco",    LocationType.STORE, "CDMX", 0),
    ("STORE-CDMX-02", "Tienda CDMX Roma",       LocationType.STORE, "CDMX", 0),
    ("STORE-CDMX-03", "Tienda CDMX Santa Fe",   LocationType.STORE, "CDMX", 0),

    # --- Tiendas NL (2) -----------------------------------------------------
    ("STORE-NL-01",   "Tienda Monterrey Centro", LocationType.STORE, "NL", 0),
    ("STORE-NL-02",   "Tienda San Pedro",        LocationType.STORE, "NL", 0),

    # --- Tiendas JAL (2) ----------------------------------------------------
    ("STORE-JAL-01",  "Tienda Guadalajara Centro", LocationType.STORE, "JAL", 0),
    ("STORE-JAL-02",  "Tienda Zapopan",            LocationType.STORE, "JAL", 0),

    # --- Tiendas EDOMEX (2) -------------------------------------------------
    ("STORE-EDOMEX-01", "Tienda Naucalpan",   LocationType.STORE, "EDOMEX", 0),
    ("STORE-EDOMEX-02", "Tienda Toluca",      LocationType.STORE, "EDOMEX", 0),

    # --- Tienda QRO (1) -----------------------------------------------------
    ("STORE-QRO-01",    "Tienda Querétaro",   LocationType.STORE, "QRO", 0),

    # --- Tienda PUE (1) -----------------------------------------------------
    ("STORE-PUE-01",    "Tienda Puebla",      LocationType.STORE, "PUE", 0),

    # --- Tienda BC (1) ------------------------------------------------------
    ("STORE-BC-01",     "Tienda Tijuana",     LocationType.STORE, "BC", 0),
]


# =============================================================================
# MATRIZ DE AFINIDAD ESTADO × CATEGORÍA
# =============================================================================
# Valores alineados con Bloque B de la planeación.
# Columnas: PLAYERAS, SUDADERAS, PANTS, SHORTS, LEGGINGS, TENIS,
#           BALONES, EQUIPO, GORRAS, MOCHILAS, BOTELLAS, CALCETINES
#
# Los valores 1.00 son el default. Los que no se listen aquí quedan en 1.00.

AFFINITY_DATA: dict[str, dict[str, Decimal]] = {
    "CDMX":   {"PLAYERAS": Decimal("1.05"), "SUDADERAS": Decimal("1.10"), "TENIS": Decimal("1.15"), "SHORTS": Decimal("0.95"), "LEGGINGS": Decimal("1.10"), "GORRAS": Decimal("1.05"), "BOTELLAS": Decimal("1.05")},
    "NL":     {"SUDADERAS": Decimal("0.90"), "TENIS": Decimal("1.10"), "SHORTS": Decimal("1.05"), "LEGGINGS": Decimal("0.95")},
    "JAL":    {"PLAYERAS": Decimal("1.05"), "TENIS": Decimal("1.05"), "GORRAS": Decimal("1.05")},
    "EDOMEX": {"SUDADERAS": Decimal("1.05"), "TENIS": Decimal("0.95"), "LEGGINGS": Decimal("1.05")},
    "QRO":    {},
    "PUE":    {"SUDADERAS": Decimal("1.05"), "TENIS": Decimal("0.95"), "GORRAS": Decimal("0.95")},
    "BC":     {"SUDADERAS": Decimal("0.85"), "TENIS": Decimal("1.10"), "SHORTS": Decimal("1.10"), "LEGGINGS": Decimal("0.95"), "GORRAS": Decimal("1.05")},
    "OAX":    {"PLAYERAS": Decimal("1.05"), "SUDADERAS": Decimal("0.85"), "TENIS": Decimal("0.90"), "GORRAS": Decimal("0.95")},
    "CHIS":   {"PLAYERAS": Decimal("1.05"), "SUDADERAS": Decimal("0.85"), "TENIS": Decimal("0.85"), "SHORTS": Decimal("1.05"), "GORRAS": Decimal("0.90")},
    "GRO":    {"SUDADERAS": Decimal("0.90"), "TENIS": Decimal("0.95"), "SHORTS": Decimal("1.05"), "GORRAS": Decimal("0.95")},
}


# =============================================================================
# SEED
# =============================================================================


def seed_states(db: Session) -> dict[str, State]:
    """Crea los 10 estados si no existen. Devuelve dict code → State."""
    result: dict[str, State] = {}

    for (
        code,
        name,
        region,
        income_group,
        population_share,
        income_index,
        online_penetration,
        regional_factor,
        growth_rate,
    ) in STATES_DATA:
        existing = db.scalar(select(State).where(State.code == code))
        if existing is not None:
            result[code] = existing
            continue

        state = State(
            id=uuid.uuid4(),
            code=code,
            name=name,
            region=region,
            income_group=income_group,
            population_share=population_share,
            income_index=income_index,
            online_penetration=online_penetration,
            regional_factor=regional_factor,
            growth_rate=growth_rate,
            status=RecordStatus.ACTIVE,
        )
        db.add(state)
        result[code] = state

    db.flush()
    return result


def seed_locations(db: Session, states: dict[str, State]) -> dict[str, Location]:
    """Crea las 15 ubicaciones si no existen. Devuelve dict code → Location."""
    result: dict[str, Location] = {}

    for code, name, location_type, state_code, capacity_units in LOCATIONS_DATA:
        existing = db.scalar(select(Location).where(Location.code == code))
        if existing is not None:
            result[code] = existing
            continue

        state = states[state_code]
        location = Location(
            id=uuid.uuid4(),
            code=code,
            name=name,
            location_type=location_type,
            state_id=state.id,
            capacity_units=capacity_units,
            status=RecordStatus.ACTIVE,
        )
        db.add(location)
        result[code] = location

    db.flush()
    return result


def seed_affinities(db: Session, states: dict[str, State]) -> int:
    """Crea las 120 afinidades si no existen. Devuelve total de nuevas."""
    categories = {
        c.code: c for c in db.scalars(select(Category)).all()
    }

    created = 0

    for state_code, state in states.items():
        affinity_by_cat = AFFINITY_DATA.get(state_code, {})

        for cat_code, category in categories.items():
            factor = affinity_by_cat.get(cat_code, Decimal("1.0000"))

            existing = db.scalar(
                select(StateCategoryAffinity).where(
                    StateCategoryAffinity.state_id == state.id,
                    StateCategoryAffinity.category_id == category.id,
                )
            )
            if existing is not None:
                continue

            affinity = StateCategoryAffinity(
                id=uuid.uuid4(),
                state_id=state.id,
                category_id=category.id,
                affinity_factor=factor,
            )
            db.add(affinity)
            created += 1

    db.flush()
    return created


def run() -> None:
    """Entry point del seed de geografía."""
    print("Seeding geography...")

    with SessionLocal() as db:
        states = seed_states(db)
        print(f"  States:      {len(states)} (idempotent)")

        locations = seed_locations(db, states)
        print(f"  Locations:   {len(locations)} (idempotent)")

        affinities_created = seed_affinities(db, states)
        print(f"  Affinities:  {affinities_created} new")

        db.commit()

    print("Geography seed done.")


if __name__ == "__main__":
    run()