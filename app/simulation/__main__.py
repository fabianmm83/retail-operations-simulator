"""Runner CLI del motor de simulación.

Uso:

    python -m app.simulation --days 30
    python -m app.simulation --days 365 --seed 12345
    python -m app.simulation --seed 42 --days 90 --scenario HIGH_DEMAND
    python -m app.simulation --reset --days 30   (borra runs previos)

Opciones:
    --days N          Número de días a simular (default: 30)
    --seed N          Seed maestro (default: 12345)
    --scenario NAME   BASELINE | HIGH_DEMAND | SUPPLY_CRISIS | ...
    --name NAME       Nombre legible del run
    --reset           Borra todos los runs previos antes de empezar
    --verbose         Logging detallado
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, func, select

from app.core.enums import SimulationRunStatus, SimulationScenario
from app.db.session import SessionLocal
from app.models.sales import Carrier, Order, OrderItem, Return, ReturnItem, Shipment
from app.models.simulation import (
    SimulationEvent,
    SimulationRun,
    SimulationSnapshot,
)
from app.simulation.engine import run_simulation


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Cuidado con Rikochet simulation engine.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Número de días a simular (default: 30)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Seed maestro para reproducibilidad (default: 12345)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="BASELINE",
        choices=[s.value for s in SimulationScenario],
        help="Escenario de simulación",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Nombre legible del run (default: auto)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra todos los runs previos antes de empezar",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Logging detallado (DEBUG)",
    )
    return parser.parse_args()


def _next_run_code(db) -> str:
    count = db.scalar(select(func.count()).select_from(SimulationRun)) or 0
    return f"RUN-{count + 1:06d}"


def _reset_runs(db) -> None:
    """Borra todos los runs previos y los datos generados por ellos.

    NO borra catálogo, geografía, clientes, inventario, suppliers, carriers.
    Solo borra orders, shipments, returns, POs, transfers, eventos, snapshots, runs.
    """
    print("Resetting simulation data (keeping seeds)...")

    # Borrar en orden de dependencia
    db.execute(delete(ReturnItem))
    db.execute(delete(Return))
    db.execute(delete(Shipment))
    db.execute(delete(OrderItem))
    db.execute(delete(Order))
    db.execute(delete(SimulationSnapshot))
    db.execute(delete(SimulationEvent))
    db.execute(delete(SimulationRun))

    # Nota: no borramos POs ni transfers para no perder el inventario inicial.
    # Si quieres reset total, ejecuta los seeds de nuevo.

    db.commit()
    print("  Simulation data reset.")


def main() -> None:
    args = _parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    with SessionLocal() as db:
        if args.reset:
            _reset_runs(db)

        # Crear el SimulationRun
        run_code = _next_run_code(db)
        name = args.name or f"Run {run_code} (seed={args.seed}, days={args.days})"

        start_date = date(2026, 1, 1)
        end_date = start_date + timedelta(days=args.days - 1)

        run = SimulationRun(
            id=uuid.uuid4(),
            run_code=run_code,
            name=name,
            description=None,
            seed=args.seed,
            scenario=SimulationScenario(args.scenario),
            config_snapshot={
                "days": args.days,
                "seed": args.seed,
                "scenario": args.scenario,
            },
            start_date=start_date,
            end_date=end_date,
            current_date=start_date,
            day_number=0,
            status=SimulationRunStatus.PENDING,
            started_at=None,
            finished_at=None,
            last_tick_at=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        print("=" * 70)
        print(f"Run:      {run.run_code}")
        print(f"Name:     {run.name}")
        print(f"Seed:     {run.seed}")
        print(f"Scenario: {run.scenario.value}")
        print(f"Days:     {args.days}")
        print(f"Dates:    {start_date} → {end_date}")
        print("=" * 70)

        try:
            run_simulation(db, run, days=args.days)
        except Exception as exc:
            print(f"\n✗ Simulation FAILED: {exc}")
            sys.exit(1)

        # Reporte final
        print("\n" + "=" * 70)
        print("RESULTADOS")
        print("=" * 70)

        orders_count = db.scalar(select(func.count()).select_from(Order)) or 0
        shipments_count = db.scalar(select(func.count()).select_from(Shipment)) or 0
        events_count = db.scalar(select(func.count()).select_from(SimulationEvent)) or 0
        snapshots_count = db.scalar(select(func.count()).select_from(SimulationSnapshot)) or 0
        revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0))) or 0

        print(f"Órdenes:          {orders_count}")
        print(f"Shipments:        {shipments_count}")
        print(f"Eventos:          {events_count}")
        print(f"Snapshots:        {snapshots_count}")
        print(f"Revenue total:    ${revenue:,.2f} MXN")
        print("=" * 70)
        print(f"\nRun {run.run_code} completed successfully.")


if __name__ == "__main__":
    main()