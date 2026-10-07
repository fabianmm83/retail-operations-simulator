"""Diagnóstico ultra-fino del día 1."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, select

from app.core.enums import (
    CustomerProfile,
    RecordStatus,
    SimulationRunStatus,
    SimulationScenario,
)
from app.db.session import SessionLocal
from app.models.customers import Customer
from app.models.sales import Order, OrderItem, Return, ReturnItem, Shipment
from app.models.simulation import SimulationEvent, SimulationRun, SimulationSnapshot
from app.simulation import engine, fulfillment
from app.simulation.rng import make_daily_rng


def _reset(db):
    db.execute(delete(ReturnItem))
    db.execute(delete(Return))
    db.execute(delete(Shipment))
    db.execute(delete(OrderItem))
    db.execute(delete(Order))
    db.execute(delete(SimulationSnapshot))
    db.execute(delete(SimulationEvent))
    db.execute(delete(SimulationRun))
    db.commit()


def run_trace(seed: int, trace_first_n: int = 20):
    with SessionLocal() as db:
        _reset(db)

        run = SimulationRun(
            id=uuid.uuid4(),
            run_code="RUN-TRACE",
            name="trace",
            seed=seed,
            scenario=SimulationScenario.BASELINE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            current_date=date(2026, 1, 1),
            day_number=0,
            status=SimulationRunStatus.PENDING,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Cargar clientes exactamente como lo hace el engine
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

        print(f"Total clientes elegibles: {len(customers)}")
        print()
        print(f"{'idx':>4} | {'customer_code':>14} | {'profile':>10} | "
              f"{'prob':>6} | {'roll':>6} | {'buy?':>5}")
        print("-" * 70)

        rng = make_daily_rng(seed, "orders", 1)

        buys = 0
        for i, c in enumerate(customers[:trace_first_n]):
            prob = engine._customer_daily_purchase_probability(c)
            roll = rng.random()
            buy = roll < prob
            if buy:
                buys += 1
            print(
                f"{i:>4} | {c.customer_code:>14} | {c.profile.value:>10} | "
                f"{prob:>6.4f} | {roll:>6.4f} | {'YES' if buy else '':>5}"
            )

        return buys


if __name__ == "__main__":
    print("=" * 70)
    print("CORRIDA 1")
    print("=" * 70)
    run_trace(12345, trace_first_n=20)

    print()
    print("=" * 70)
    print("CORRIDA 2")
    print("=" * 70)
    run_trace(12345, trace_first_n=20)