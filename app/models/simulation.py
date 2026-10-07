"""Modelos del motor de simulación (M7).

Define:

- SimulationRun        : control de una corrida de simulación
- SimulationEvent      : evento puntual con duración, scope y factor
- SimulationSnapshot   : fotografía consolidada del estado en un día

Jerarquía:
    SimulationRun 1 ── N SimulationEvent
    SimulationRun 1 ── N SimulationSnapshot
    SimulationEvent N ── 1 SimulationEvent (parent, para cascadas)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    SimulationEventScope,
    SimulationEventStatus,
    SimulationEventTrigger,
    SimulationEventType,
    SimulationRunStatus,
    SimulationScenario,
)
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


# =============================================================================
# SIMULATION RUN
# =============================================================================


class SimulationRun(UUIDMixin, TimestampMixin, Base):
    """Control de una corrida de simulación.

    Contiene el seed maestro, las fechas simuladas, el escenario y
    un snapshot de la configuración usada. Un run es reproducible:
    mismo seed + misma config → misma secuencia de eventos y datos.
    """

    __tablename__ = "simulation_runs"

    # -------------------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------------------

    run_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment="Código de negocio: RUN-000001",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # Parámetros
    # -------------------------------------------------------------------------

    seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Seed maestro para reproducibilidad",
    )

    scenario: Mapped[SimulationScenario] = mapped_column(
        SAEnum(
            SimulationScenario,
            name="simulation_scenario",
            create_type=True,
        ),
        nullable=False,
        server_default=SimulationScenario.BASELINE.value,
    )

    config_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot congelado de la configuración (parámetros A–F)",
    )

    # -------------------------------------------------------------------------
    # Fechas simuladas
    # -------------------------------------------------------------------------

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha simulada de inicio",
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha simulada de fin (null si abierto)",
    )

    current_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha simulada actual",
    )

    day_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Contador de días desde start_date",
    )

    # -------------------------------------------------------------------------
    # Estado
    # -------------------------------------------------------------------------

    status: Mapped[SimulationRunStatus] = mapped_column(
        SAEnum(
            SimulationRunStatus,
            name="simulation_run_status",
            create_type=True,
        ),
        nullable=False,
        server_default=SimulationRunStatus.PENDING.value,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp real de inicio del run",
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp real de fin del run",
    )

    last_tick_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp real del último día procesado",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    events: Mapped[list["SimulationEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    snapshots: Mapped[list["SimulationSnapshot"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "run_code = UPPER(run_code)",
            name="simulation_runs_code_upper",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="simulation_runs_end_after_start",
        ),
        CheckConstraint(
            "current_date >= start_date",
            name="simulation_runs_current_after_start",
        ),
        CheckConstraint(
            "day_number >= 0",
            name="simulation_runs_day_number_nonnegative",
        ),
        Index("ix_simulation_runs_status", "status"),
        Index("ix_simulation_runs_scenario", "scenario"),
        Index("ix_simulation_runs_current_date", "current_date"),
    )

    def __repr__(self) -> str:
        return f"<SimulationRun {self.run_code} ({self.status})>"


# =============================================================================
# SIMULATION EVENT
# =============================================================================


class SimulationEvent(UUIDMixin, TimestampMixin, Base):
    """Evento que altera las condiciones normales durante su vigencia.

    Un evento tiene scope (GLOBAL, STATE, CATEGORY, PRODUCT, ...), un
    factor de impacto, y un rango de fechas simuladas en el que está
    activo. Los eventos cascada referencian al evento que los disparó
    vía `parent_event_id`.
    """

    __tablename__ = "simulation_events"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_events.id", ondelete="SET NULL"),
        nullable=True,
        comment="Evento padre si este es una cascada",
    )

    # -------------------------------------------------------------------------
    # Tipo y scope
    # -------------------------------------------------------------------------

    event_type: Mapped[SimulationEventType] = mapped_column(
        SAEnum(
            SimulationEventType,
            name="simulation_event_type",
            create_type=True,
        ),
        nullable=False,
    )

    scope_type: Mapped[SimulationEventScope] = mapped_column(
        SAEnum(
            SimulationEventScope,
            name="simulation_event_scope",
            create_type=True,
        ),
        nullable=False,
    )

    scope_value: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Código del scope (CDMX, PLAYERAS, PLY-W-0001, ...). Null si GLOBAL",
    )

    # -------------------------------------------------------------------------
    # Vigencia y factor
    # -------------------------------------------------------------------------

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    impact_factor: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        nullable=False,
        comment="Multiplicador de impacto (puede ser <1, >1 o negativo)",
    )

    # -------------------------------------------------------------------------
    # Estado
    # -------------------------------------------------------------------------

    status: Mapped[SimulationEventStatus] = mapped_column(
        SAEnum(
            SimulationEventStatus,
            name="simulation_event_status",
            create_type=True,
        ),
        nullable=False,
        server_default=SimulationEventStatus.SCHEDULED.value,
    )

    trigger: Mapped[SimulationEventTrigger] = mapped_column(
        SAEnum(
            SimulationEventTrigger,
            name="simulation_event_trigger",
            create_type=True,
        ),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detalles libres del evento (causas, referencias, notas)",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    run: Mapped["SimulationRun"] = relationship(
        back_populates="events",
    )

    parent_event: Mapped["SimulationEvent | None"] = relationship(
        remote_side="SimulationEvent.id",
        back_populates="cascade_children",
    )

    cascade_children: Mapped[list["SimulationEvent"]] = relationship(
        back_populates="parent_event",
        lazy="selectin",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="simulation_events_end_after_start",
        ),
        CheckConstraint(
            "(scope_type = 'GLOBAL' AND scope_value IS NULL) OR "
            "(scope_type <> 'GLOBAL' AND scope_value IS NOT NULL)",
            name="simulation_events_scope_coherent",
        ),
        Index("ix_simulation_events_run", "run_id"),
        Index("ix_simulation_events_type", "event_type"),
        Index("ix_simulation_events_scope", "scope_type", "scope_value"),
        Index("ix_simulation_events_dates", "start_date", "end_date"),
        Index("ix_simulation_events_status", "status"),
        Index("ix_simulation_events_parent", "parent_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SimulationEvent {self.event_type} "
            f"scope={self.scope_type}:{self.scope_value}>"
        )


# =============================================================================
# SIMULATION SNAPSHOT
# =============================================================================


class SimulationSnapshot(UUIDMixin, TimestampMixin, Base):
    """Fotografía consolidada del estado en un día simulado.

    Sirve para:
    - reanudar sin reprocesar
    - análisis histórico del estado
    - comparar escenarios
    """

    __tablename__ = "simulation_snapshots"

    # -------------------------------------------------------------------------
    # Relaciones
    # -------------------------------------------------------------------------

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Fecha simulada
    # -------------------------------------------------------------------------

    day_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Contenido
    # -------------------------------------------------------------------------

    data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Totales, KPIs y estado consolidado del día",
    )

    # -------------------------------------------------------------------------
    # Relaciones ORM
    # -------------------------------------------------------------------------

    run: Mapped["SimulationRun"] = relationship(
        back_populates="snapshots",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "day_number >= 0",
            name="simulation_snapshots_day_number_nonnegative",
        ),
        Index("ix_simulation_snapshots_run", "run_id"),
        Index(
            "ux_simulation_snapshots_run_day",
            "run_id",
            "day_number",
            unique=True,
        ),
        Index("ix_simulation_snapshots_date", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<SimulationSnapshot run={self.run_id} "
            f"day={self.day_number} date={self.snapshot_date}>"
        )