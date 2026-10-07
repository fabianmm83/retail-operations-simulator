"""007 create simulation tables

Revision ID: 58f65b4ae46a
Revises: a4bf27e873c5
Create Date: 2026-10-06 20:52:47.251003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '58f65b4ae46a'
down_revision: Union[str, Sequence[str], None] = 'a4bf27e873c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- Crear enums nuevos de M7 (no existen todavía) ---------------------
    postgresql.ENUM(
        'BASELINE', 'HIGH_DEMAND', 'SUPPLY_CRISIS', 'LOGISTICS_CRISIS',
        'ECONOMIC_DOWNTURN', 'PEAK_SEASON', 'STRESS_TEST',
        name='simulation_scenario',
    ).create(op.get_bind())

    postgresql.ENUM(
        'PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED',
        name='simulation_run_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'NORMAL_OPERATION', 'HIGH_DEMAND', 'BLACK_FRIDAY', 'BUEN_FIN',
        'HOT_SALE', 'SEASONAL_PEAK', 'DEMAND_DROP', 'PRODUCT_LAUNCH',
        'PROMOTION', 'SUPPLIER_DELAY', 'SUPPLIER_OUTAGE',
        'WAREHOUSE_DELAY', 'WAREHOUSE_OVERLOAD', 'CARRIER_DELAY',
        'LOST_SHIPMENT', 'STOCKOUT', 'PRODUCT_RETURN', 'PAYMENT_FAILURE',
        'ORDER_CANCELLATION', 'PRICE_CHANGE',
        name='simulation_event_type',
    ).create(op.get_bind())

    postgresql.ENUM(
        'GLOBAL', 'STATE', 'CATEGORY', 'PRODUCT',
        'SUPPLIER', 'CARRIER', 'WAREHOUSE',
        name='simulation_event_scope',
    ).create(op.get_bind())

    postgresql.ENUM(
        'SCHEDULED', 'ACTIVE', 'FINISHED', 'CANCELLED',
        name='simulation_event_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'SCHEDULED', 'RANDOM', 'MANUAL', 'CASCADE',
        name='simulation_event_trigger',
    ).create(op.get_bind())

    # --- Tabla simulation_runs ---------------------------------------------
    op.create_table('simulation_runs',
    sa.Column('run_code', sa.String(length=30), nullable=False, comment='Código de negocio: RUN-000001'),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('seed', sa.Integer(), nullable=False, comment='Seed maestro para reproducibilidad'),
    sa.Column('scenario', postgresql.ENUM('BASELINE', 'HIGH_DEMAND', 'SUPPLY_CRISIS', 'LOGISTICS_CRISIS', 'ECONOMIC_DOWNTURN', 'PEAK_SEASON', 'STRESS_TEST', name='simulation_scenario', create_type=False), server_default='BASELINE', nullable=False),
    sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Snapshot congelado de la configuración (parámetros A–F)'),
    sa.Column('start_date', sa.Date(), nullable=False, comment='Fecha simulada de inicio'),
    sa.Column('end_date', sa.Date(), nullable=True, comment='Fecha simulada de fin (null si abierto)'),
    sa.Column('current_date', sa.Date(), nullable=False, comment='Fecha simulada actual'),
    sa.Column('day_number', sa.Integer(), server_default='0', nullable=False, comment='Contador de días desde start_date'),
    sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', name='simulation_run_status', create_type=False), server_default='PENDING', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp real de inicio del run'),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp real de fin del run'),
    sa.Column('last_tick_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp real del último día procesado'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('current_date >= start_date', name='simulation_runs_current_after_start'),
    sa.CheckConstraint('day_number >= 0', name='simulation_runs_day_number_nonnegative'),
    sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='simulation_runs_end_after_start'),
    sa.CheckConstraint('run_code = UPPER(run_code)', name='simulation_runs_code_upper'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_code')
    )
    op.create_index('ix_simulation_runs_current_date', 'simulation_runs', ['current_date'], unique=False)
    op.create_index('ix_simulation_runs_scenario', 'simulation_runs', ['scenario'], unique=False)
    op.create_index('ix_simulation_runs_status', 'simulation_runs', ['status'], unique=False)

    # --- Tabla simulation_events -------------------------------------------
    op.create_table('simulation_events',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('parent_event_id', sa.UUID(), nullable=True, comment='Evento padre si este es una cascada'),
    sa.Column('event_type', postgresql.ENUM('NORMAL_OPERATION', 'HIGH_DEMAND', 'BLACK_FRIDAY', 'BUEN_FIN', 'HOT_SALE', 'SEASONAL_PEAK', 'DEMAND_DROP', 'PRODUCT_LAUNCH', 'PROMOTION', 'SUPPLIER_DELAY', 'SUPPLIER_OUTAGE', 'WAREHOUSE_DELAY', 'WAREHOUSE_OVERLOAD', 'CARRIER_DELAY', 'LOST_SHIPMENT', 'STOCKOUT', 'PRODUCT_RETURN', 'PAYMENT_FAILURE', 'ORDER_CANCELLATION', 'PRICE_CHANGE', name='simulation_event_type', create_type=False), nullable=False),
    sa.Column('scope_type', postgresql.ENUM('GLOBAL', 'STATE', 'CATEGORY', 'PRODUCT', 'SUPPLIER', 'CARRIER', 'WAREHOUSE', name='simulation_event_scope', create_type=False), nullable=False),
    sa.Column('scope_value', sa.String(length=50), nullable=True, comment='Código del scope (CDMX, PLAYERAS, PLY-W-0001, ...). Null si GLOBAL'),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('impact_factor', sa.Numeric(precision=6, scale=4), nullable=False, comment='Multiplicador de impacto (puede ser <1, >1 o negativo)'),
    sa.Column('status', postgresql.ENUM('SCHEDULED', 'ACTIVE', 'FINISHED', 'CANCELLED', name='simulation_event_status', create_type=False), server_default='SCHEDULED', nullable=False),
    sa.Column('trigger', postgresql.ENUM('SCHEDULED', 'RANDOM', 'MANUAL', 'CASCADE', name='simulation_event_trigger', create_type=False), nullable=False),
    sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Detalles libres del evento (causas, referencias, notas)'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(scope_type = 'GLOBAL' AND scope_value IS NULL) OR (scope_type <> 'GLOBAL' AND scope_value IS NOT NULL)", name='simulation_events_scope_coherent'),
    sa.CheckConstraint('end_date >= start_date', name='simulation_events_end_after_start'),
    sa.ForeignKeyConstraint(['parent_event_id'], ['simulation_events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['run_id'], ['simulation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_simulation_events_dates', 'simulation_events', ['start_date', 'end_date'], unique=False)
    op.create_index('ix_simulation_events_parent', 'simulation_events', ['parent_event_id'], unique=False)
    op.create_index('ix_simulation_events_run', 'simulation_events', ['run_id'], unique=False)
    op.create_index('ix_simulation_events_scope', 'simulation_events', ['scope_type', 'scope_value'], unique=False)
    op.create_index('ix_simulation_events_status', 'simulation_events', ['status'], unique=False)
    op.create_index('ix_simulation_events_type', 'simulation_events', ['event_type'], unique=False)

    # --- Tabla simulation_snapshots ----------------------------------------
    op.create_table('simulation_snapshots',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('day_number', sa.Integer(), nullable=False),
    sa.Column('snapshot_date', sa.Date(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Totales, KPIs y estado consolidado del día'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('day_number >= 0', name='simulation_snapshots_day_number_nonnegative'),
    sa.ForeignKeyConstraint(['run_id'], ['simulation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_simulation_snapshots_date', 'simulation_snapshots', ['snapshot_date'], unique=False)
    op.create_index('ix_simulation_snapshots_run', 'simulation_snapshots', ['run_id'], unique=False)
    op.create_index('ux_simulation_snapshots_run_day', 'simulation_snapshots', ['run_id', 'day_number'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_simulation_snapshots_run_day', table_name='simulation_snapshots')
    op.drop_index('ix_simulation_snapshots_run', table_name='simulation_snapshots')
    op.drop_index('ix_simulation_snapshots_date', table_name='simulation_snapshots')
    op.drop_table('simulation_snapshots')
    op.drop_index('ix_simulation_events_type', table_name='simulation_events')
    op.drop_index('ix_simulation_events_status', table_name='simulation_events')
    op.drop_index('ix_simulation_events_scope', table_name='simulation_events')
    op.drop_index('ix_simulation_events_run', table_name='simulation_events')
    op.drop_index('ix_simulation_events_parent', table_name='simulation_events')
    op.drop_index('ix_simulation_events_dates', table_name='simulation_events')
    op.drop_table('simulation_events')
    op.drop_index('ix_simulation_runs_status', table_name='simulation_runs')
    op.drop_index('ix_simulation_runs_scenario', table_name='simulation_runs')
    op.drop_index('ix_simulation_runs_current_date', table_name='simulation_runs')
    op.drop_table('simulation_runs')

    # --- Eliminar enums nuevos de M7 ---------------------------------------
    postgresql.ENUM(name='simulation_event_trigger').drop(op.get_bind())
    postgresql.ENUM(name='simulation_event_status').drop(op.get_bind())
    postgresql.ENUM(name='simulation_event_scope').drop(op.get_bind())
    postgresql.ENUM(name='simulation_event_type').drop(op.get_bind())
    postgresql.ENUM(name='simulation_run_status').drop(op.get_bind())
    postgresql.ENUM(name='simulation_scenario').drop(op.get_bind())