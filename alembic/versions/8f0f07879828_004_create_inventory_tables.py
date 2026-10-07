"""004 create inventory tables

Revision ID: 8f0f07879828
Revises: 36f36181cb96
Create Date: 2026-10-06 19:58:48.088097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8f0f07879828'
down_revision: Union[str, Sequence[str], None] = '36f36181cb96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- Crear enums nuevos de M4 (no existen todavía) ---------------------
    postgresql.ENUM(
        'PENDING', 'IN_TRANSIT', 'RECEIVED', 'CANCELLED',
        name='transfer_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'NORMAL', 'REORDER', 'CRITICAL', 'STOCKOUT',
        name='stock_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'SALE', 'PURCHASE_RECEIPT', 'RETURN', 'ADJUSTMENT',
        'DAMAGE', 'TRANSFER_OUT', 'TRANSFER_IN',
        name='movement_type',
    ).create(op.get_bind())

    # --- Tabla transfers ---------------------------------------------------
    op.create_table('transfers',
    sa.Column('transfer_code', sa.String(length=30), nullable=False, comment='Código de negocio: TRF-2026-000001'),
    sa.Column('origin_location_id', sa.UUID(), nullable=False),
    sa.Column('destination_location_id', sa.UUID(), nullable=False),
    sa.Column('status', postgresql.ENUM('PENDING', 'IN_TRANSIT', 'RECEIVED', 'CANCELLED', name='transfer_status', create_type=False), server_default='PENDING', nullable=False),
    sa.Column('requested_date', sa.Date(), nullable=False, comment='Fecha en que se solicita la transferencia'),
    sa.Column('shipped_date', sa.Date(), nullable=True, comment='Fecha en que sale del origen'),
    sa.Column('received_date', sa.Date(), nullable=True, comment='Fecha en que llega al destino'),
    sa.Column('expected_arrival_date', sa.Date(), nullable=True, comment='Fecha estimada de llegada'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('origin_location_id <> destination_location_id', name='transfers_origin_ne_destination'),
    sa.CheckConstraint('received_date IS NULL OR received_date >= shipped_date', name='transfers_received_after_shipped'),
    sa.CheckConstraint('shipped_date IS NULL OR shipped_date >= requested_date', name='transfers_shipped_after_requested'),
    sa.CheckConstraint('transfer_code = UPPER(transfer_code)', name='transfers_code_upper'),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['origin_location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('transfer_code')
    )
    op.create_index('ix_transfers_destination', 'transfers', ['destination_location_id'], unique=False)
    op.create_index('ix_transfers_origin', 'transfers', ['origin_location_id'], unique=False)
    op.create_index('ix_transfers_requested_date', 'transfers', ['requested_date'], unique=False)
    op.create_index('ix_transfers_status', 'transfers', ['status'], unique=False)

    # --- Tabla inventory ---------------------------------------------------
    op.create_table('inventory',
    sa.Column('variant_id', sa.UUID(), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('quantity', sa.Integer(), server_default='0', nullable=False, comment='Cantidad física en piso/almacén'),
    sa.Column('reserved_quantity', sa.Integer(), server_default='0', nullable=False, comment='Cantidad comprometida a órdenes pendientes'),
    sa.Column('available_quantity', sa.Integer(), sa.Computed('quantity - reserved_quantity', persisted=True), nullable=False, comment='quantity - reserved_quantity (GENERATED)'),
    sa.Column('reorder_point', sa.Integer(), server_default='0', nullable=False, comment='Umbral de reposición (avail <= rp → REORDER)'),
    sa.Column('safety_stock', sa.Integer(), server_default='0', nullable=False, comment='Colchón de seguridad (avail <= ss → CRITICAL)'),
    sa.Column('max_stock', sa.Integer(), server_default='0', nullable=False, comment='Tope de inventario (4× reorder point)'),
    sa.Column('stock_status', postgresql.ENUM('NORMAL', 'REORDER', 'CRITICAL', 'STOCKOUT', name='stock_status', create_type=False), server_default='NORMAL', nullable=False, comment='Estado calculado del stock en esta ubicación'),
    sa.Column('last_movement_date', sa.Date(), nullable=True, comment='Fecha del último movimiento'),
    sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='record_status', create_type=False), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('max_stock >= reorder_point', name='inventory_max_gte_reorder'),
    sa.CheckConstraint('quantity >= 0', name='inventory_quantity_nonnegative'),
    sa.CheckConstraint('reorder_point >= 0', name='inventory_reorder_point_nonnegative'),
    sa.CheckConstraint('reserved_quantity <= quantity', name='inventory_reserved_lte_quantity'),
    sa.CheckConstraint('reserved_quantity >= 0', name='inventory_reserved_nonnegative'),
    sa.CheckConstraint('safety_stock <= reorder_point', name='inventory_safety_lte_reorder'),
    sa.CheckConstraint('safety_stock >= 0', name='inventory_safety_stock_nonnegative'),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('variant_id', 'location_id', name='inventory_unique_variant_location')
    )
    op.create_index('ix_inventory_location', 'inventory', ['location_id'], unique=False)
    op.create_index('ix_inventory_status', 'inventory', ['stock_status'], unique=False)
    op.create_index('ix_inventory_variant', 'inventory', ['variant_id'], unique=False)

    # --- Tabla inventory_movements -----------------------------------------
    op.create_table('inventory_movements',
    sa.Column('variant_id', sa.UUID(), nullable=False),
    sa.Column('location_id', sa.UUID(), nullable=False),
    sa.Column('movement_type', postgresql.ENUM('SALE', 'PURCHASE_RECEIPT', 'RETURN', 'ADJUSTMENT', 'DAMAGE', 'TRANSFER_OUT', 'TRANSFER_IN', name='movement_type', create_type=False), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False, comment='Delta: positivo (entrada) o negativo (salida). Nunca cero.'),
    sa.Column('reference_type', sa.String(length=30), nullable=True, comment='ORDER · PURCHASE_ORDER · TRANSFER · EVENT · MANUAL'),
    sa.Column('reference_id', sa.UUID(), nullable=True, comment='ID del objeto origen (order, PO, transfer, event)'),
    sa.Column('movement_date', sa.Date(), nullable=False, comment='Fecha simulada del movimiento'),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity <> 0', name='inventory_movement_quantity_nonzero'),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_movements_location_date', 'inventory_movements', ['location_id', 'movement_date'], unique=False)
    op.create_index('ix_movements_reference', 'inventory_movements', ['reference_type', 'reference_id'], unique=False)
    op.create_index('ix_movements_type', 'inventory_movements', ['movement_type'], unique=False)
    op.create_index('ix_movements_variant_date', 'inventory_movements', ['variant_id', 'movement_date'], unique=False)

    # --- Tabla transfer_items ----------------------------------------------
    op.create_table('transfer_items',
    sa.Column('transfer_id', sa.UUID(), nullable=False),
    sa.Column('variant_id', sa.UUID(), nullable=False),
    sa.Column('quantity_requested', sa.Integer(), nullable=False),
    sa.Column('quantity_shipped', sa.Integer(), server_default='0', nullable=False, comment='Cantidad realmente enviada (puede ser < requested)'),
    sa.Column('quantity_received', sa.Integer(), server_default='0', nullable=False, comment='Cantidad realmente recibida (puede ser < shipped)'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity_received <= quantity_shipped', name='transfer_items_received_lte_shipped'),
    sa.CheckConstraint('quantity_received >= 0', name='transfer_items_received_nonnegative'),
    sa.CheckConstraint('quantity_requested > 0', name='transfer_items_requested_positive'),
    sa.CheckConstraint('quantity_shipped <= quantity_requested', name='transfer_items_shipped_lte_requested'),
    sa.CheckConstraint('quantity_shipped >= 0', name='transfer_items_shipped_nonnegative'),
    sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('transfer_id', 'variant_id', name='transfer_items_unique_transfer_variant')
    )
    op.create_index('ix_transfer_items_transfer', 'transfer_items', ['transfer_id'], unique=False)
    op.create_index('ix_transfer_items_variant', 'transfer_items', ['variant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_transfer_items_variant', table_name='transfer_items')
    op.drop_index('ix_transfer_items_transfer', table_name='transfer_items')
    op.drop_table('transfer_items')
    op.drop_index('ix_movements_variant_date', table_name='inventory_movements')
    op.drop_index('ix_movements_type', table_name='inventory_movements')
    op.drop_index('ix_movements_reference', table_name='inventory_movements')
    op.drop_index('ix_movements_location_date', table_name='inventory_movements')
    op.drop_table('inventory_movements')
    op.drop_index('ix_inventory_variant', table_name='inventory')
    op.drop_index('ix_inventory_status', table_name='inventory')
    op.drop_index('ix_inventory_location', table_name='inventory')
    op.drop_table('inventory')
    op.drop_index('ix_transfers_status', table_name='transfers')
    op.drop_index('ix_transfers_requested_date', table_name='transfers')
    op.drop_index('ix_transfers_origin', table_name='transfers')
    op.drop_index('ix_transfers_destination', table_name='transfers')
    op.drop_table('transfers')

    # --- Eliminar enums nuevos de M4 ---------------------------------------
    postgresql.ENUM(name='movement_type').drop(op.get_bind())
    postgresql.ENUM(name='stock_status').drop(op.get_bind())
    postgresql.ENUM(name='transfer_status').drop(op.get_bind())