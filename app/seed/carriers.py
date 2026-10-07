"""Seed de carriers (M6).

Genera los 5 transportistas definidos en el Bloque F.

Los carriers son datos estáticos. Las órdenes, shipments y returns
NO se siembran: se generan durante la simulación (M7).

Uso:
    python -m app.seed.carriers
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import CarrierCoverage, RecordStatus
from app.db.session import SessionLocal
from app.models.sales import Carrier


# =============================================================================
# DATOS DE LOS 5 CARRIERS
# =============================================================================
# Formato:
#   (carrier_code, name, coverage, base_lead_time_days, max_lead_time_days,
#    reliability, base_cost, cost_multiplier)
#
# Valores alineados con el Bloque F:
#   - CAR-01: nacional, rápido, confiable, costo base
#   - CAR-02: norte, rápido, confiable, más barato
#   - CAR-03: centro, medio, confiable, barato
#   - CAR-04: nacional, express, caro
#   - CAR-05: nacional, económico, lento, menos confiable

CARRIERS_DATA = [
    ("CAR-01", "Envíos Rápidos MX",   CarrierCoverage.NATIONAL, 2, 4, Decimal("0.96"), Decimal("89.00"),  Decimal("1.0000")),
    ("CAR-02", "Paquetería del Norte", CarrierCoverage.NORTH,    2, 3, Decimal("0.94"), Decimal("79.00"),  Decimal("0.9500")),
    ("CAR-03", "Logística Centro",     CarrierCoverage.CENTER,   3, 5, Decimal("0.92"), Decimal("75.00"),  Decimal("0.9000")),
    ("CAR-04", "Express Nacional",     CarrierCoverage.NATIONAL, 1, 2, Decimal("0.97"), Decimal("139.00"), Decimal("1.3500")),
    ("CAR-05", "Económico MX",         CarrierCoverage.NATIONAL, 4, 7, Decimal("0.88"), Decimal("59.00"),  Decimal("0.7500")),
]


# =============================================================================
# SEED
# =============================================================================


def seed_carriers(db: Session) -> int:
    """Crea los 5 carriers si no existen. Devuelve total creado."""
    existing_count = db.scalar(select(func.count()).select_from(Carrier)) or 0
    if existing_count > 0:
        print(f"  Carriers:   {existing_count} already exist, skipping")
        return 0

    created = 0

    for (
        carrier_code,
        name,
        coverage,
        base_lead_time,
        max_lead_time,
        reliability,
        base_cost,
        cost_multiplier,
    ) in CARRIERS_DATA:
        existing = db.scalar(
            select(Carrier).where(Carrier.carrier_code == carrier_code)
        )
        if existing is not None:
            continue

        carrier = Carrier(
            id=uuid.uuid4(),
            carrier_code=carrier_code,
            name=name,
            coverage=coverage,
            base_lead_time_days=base_lead_time,
            max_lead_time_days=max_lead_time,
            reliability=reliability,
            base_cost=base_cost,
            cost_multiplier=cost_multiplier,
            status=RecordStatus.ACTIVE,
        )
        db.add(carrier)
        created += 1

    db.flush()
    return created


def run() -> None:
    """Entry point del seed de carriers."""
    print("Seeding carriers...")

    with SessionLocal() as db:
        created = seed_carriers(db)
        print(f"  Carriers:   {created} new")
        db.commit()

    print("Carriers seed done.")


if __name__ == "__main__":
    run()