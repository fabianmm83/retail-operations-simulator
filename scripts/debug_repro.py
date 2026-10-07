"""Diagnóstico de reproducibilidad: corre el motor 2 veces con el mismo
seed y compara el estado al final de cada día.

Uso:
    python scripts/debug_repro.py --days 1
    python scripts/debug_repro.py --days 2
    python scripts/debug_repro.py --days 3
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from datetime import date

from sqlalchemy import delete, select

from app.core.enums import SimulationRunStatus, SimulationScenario
from app.db.session import SessionLocal
from app.models.sales import (
    Order,
    OrderItem,
    Return,
    ReturnItem,
    Shipment,
)
from app.models.simulation import (
    SimulationEvent,
    SimulationRun,
    SimulationSnapshot,
)
from app.simulation import engine


# =============================================================================
# UTILIDADES
# =============================================================================


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--seed", type=int, default=12345)
    return parser.parse_args()


def _reset(db) -> None:
    """Limpia todo lo que genera el motor."""
    db.execute(delete(ReturnItem))
    db.execute(delete(Return))
    db.execute(delete(Shipment))
    db.execute(delete(OrderItem))
    db.execute(delete(Order))
    db.execute(delete(SimulationSnapshot))
    db.execute(delete(SimulationEvent))
    db.execute(delete(SimulationRun))
    db.commit()


def _hash_orders(db) -> tuple[str, int, str]:
    """Devuelve (hash, count, first_order_info)."""
    orders = list(
        db.scalars(select(Order).order_by(Order.order_number)).all()
    )
    hasher = hashlib.sha256()
    for o in orders:
        line = (
            f"{o.order_number}|{o.customer_id}|{o.channel.value}|"
            f"{o.subtotal}|{o.total}"
        )
        hasher.update(line.encode())

    if not orders:
        return hasher.hexdigest(), 0, "(no orders)"

    first = orders[0]
    info = (
        f"{first.order_number}|{first.customer_id}|"
        f"{first.channel.value}|{first.total}"
    )
    return hasher.hexdigest(), len(orders), info


# =============================================================================
# RUN
# =============================================================================


def _run_once(seed: int, days: int) -> dict:
    """Corre el motor y devuelve un dict con el estado por día.

    Importante: hace `flush()` antes de hashear cada día para forzar
    los INSERTs pendientes (Order, OrderItem, etc.) sin hacer commit.
    """
    with SessionLocal() as db:
        _reset(db)

        run = SimulationRun(
            id=uuid.uuid4(),
            run_code="RUN-DEBUG",
            name="debug",
            seed=seed,
            scenario=SimulationScenario.BASELINE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1 + days),
            current_date=date(2026, 1, 1),
            day_number=0,
            status=SimulationRunStatus.PENDING,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        original_close = engine.phase_8_close_day
        day_hashes: list[tuple[int, str, int, str]] = []

        def patched_close(db_, ctx_, stats_):
            original_close(db_, ctx_, stats_)
            db_.flush()
            h, c, f = _hash_orders(db_)
            day_hashes.append((ctx_.run.day_number, h, c, f))

        engine.phase_8_close_day = patched_close
        try:
            engine.run_simulation(db, run, days=days)
        finally:
            engine.phase_8_close_day = original_close

        h_final, c_final, f_final = _hash_orders(db)

        return {
            "day_hashes": day_hashes,
            "final_hash": h_final,
            "final_count": c_final,
            "final_first": f_final,
        }


def main() -> None:
    args = _parse_args()

    print(f"Seed: {args.seed}   Days: {args.days}\n")

    print("=" * 70)
    print("CORRIDA 1")
    print("=" * 70)
    r1 = _run_once(args.seed, args.days)
    for day, h, c, f in r1["day_hashes"]:
        print(f"  Día {day}: {h[:16]}...  orders={c}  first={f}")

    print()
    print("=" * 70)
    print("CORRIDA 2")
    print("=" * 70)
    r2 = _run_once(args.seed, args.days)
    for day, h, c, f in r2["day_hashes"]:
        print(f"  Día {day}: {h[:16]}...  orders={c}  first={f}")

    print()
    print("=" * 70)
    print("COMPARACIÓN")
    print("=" * 70)

    all_equal = True
    for (d1, h1, c1, f1), (d2, h2, c2, f2) in zip(
        r1["day_hashes"], r2["day_hashes"]
    ):
        same_hash = h1 == h2
        same_count = c1 == c2
        same_first = f1 == f2

        marker = "✓" if (same_hash and same_count and same_first) else "✗"
        if not (same_hash and same_count and same_first):
            all_equal = False

        print(f"  {marker} Día {d1}:")
        print(f"      hash:  {'igual' if same_hash else 'DIFERENTE'}")
        print(
            f"      count: {'igual' if same_count else f'DIFERENTE ({c1} vs {c2})'}"
        )
        print(f"      first: {'igual' if same_first else 'DIFERENTE'}")
        if not same_first:
            print(f"             c1: {f1}")
            print(f"             c2: {f2}")

    print()
    print("=" * 70)
    if all_equal:
        print("✓ REPRODUCIBILIDAD OK")
    else:
        print("✗ NO REPRODUCIBLE — primer día divergente: el marcado con ✗")
    print("=" * 70)


if __name__ == "__main__":
    main()