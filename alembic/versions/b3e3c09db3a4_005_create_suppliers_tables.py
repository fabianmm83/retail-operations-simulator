"""005 create suppliers tables

Revision ID: b3e3c09db3a4
Revises: 8f0f07879828
Create Date: 2026-10-06 20:22:21.697028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3e3c09db3a4'
down_revision: Union[str, Sequence[str], None] = '8f0f07879828'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- Crear enums nuevos de M5 (no existen todavía) ---------------------
    postgresql.ENUM(
        'LARGE_NATIONAL', 'MEDIUM_NATIONAL', 'IMPORTED',
        name='supplier_type',
    ).create(op.get_bind())

    postgresql.ENUM(
        'PENDING', 'CONFIRMED', 'IN_TRANSIT', 'RECEIVED', 'PARTIAL', 'CANCELLED',
        name='purchase_order_status',
    ).create(op.get_bind())

    # --- Tabla suppliers ---------------------------------------------------
    op.create_table('suppliers',
    sa.Column('supplier_code', sa.String(length=20), nullable=False, comment='Código de negocio: SUP-N01, SUP-M01, SUP-I01'),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('supplier_type', postgresql.ENUM('LARGE_NATIONAL', 'MEDIUM_NATIONAL', 'IMPORTED', name='supplier_type', create_type=False), nullable=False),
    sa.Column('state_id', sa.UUID(), nullable=False, comment='Estado base de operaciones del proveedor'),
    sa.Column('lead_time_days', sa.Integer(), nullable=False, comment='Lead time promedio en días'),
    sa.Column('reliability', sa.Numeric(precision=5, scale=4), nullable=False, comment='Confiabilidad (0.0000–1.0000)'),
    sa.Column('minimum_order_quantity', sa.Integer(), nullable=False, comment='MOQ: cantidad mínima por línea de compra'),
    sa.Column('volume_discount', sa.Numeric(precision=5, scale=4), server_default='0', nullable=False, comment='Descuento por volumen (0.05 = 5%)'),
    sa.Column('cost_multiplier', sa.Numeric(precision=5, scale=4), server_default='1.0', nullable=False, comment='Multiplicador sobre base_cost (1.0 = base)'),
    sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='record_status', create_type=False), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('cost_multiplier > 0', name='suppliers_cost_multiplier_positive'),
    sa.CheckConstraint('lead_time_days > 0', name='suppliers_lead_time_positive'),
    sa.CheckConstraint('minimum_order_quantity > 0', name='suppliers_moq_positive'),
    sa.CheckConstraint('reliability >= 0.5 AND reliability <= 1.0', name='suppliers_reliability_range'),
    sa.CheckConstraint('supplier_code = UPPER(supplier_code)', name='suppliers_code_upper'),
    sa.CheckConstraint('volume_discount >= 0 AND volume_discount <= 0.5', name='suppliers_volume_discount_range'),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('supplier_code')
    )
    op.create_index('ix_suppliers_state', 'suppliers', ['state_id'], unique=False)
    op.create_index('ix_suppliers_status', 'suppliers', ['status'], unique=False)
    op.create_index('ix_suppliers_type', 'suppliers', ['supplier_type'], unique=False)

    # --- Tabla purchase_orders ---------------------------------------------
    op.create_table('purchase_orders',
    sa.Column('po_number', sa.String(length=30), nullable=False, comment='Código de negocio: PO-2026-000001'),
    sa.Column('supplier_id', sa.UUID(), nullable=False),
    sa.Column('destination_location_id', sa.UUID(), nullable=False, comment='CEDIS destino de la orden'),
    sa.Column('status', postgresql.ENUM('PENDING', 'CONFIRMED', 'IN_TRANSIT', 'RECEIVED', 'PARTIAL', 'CANCELLED', name='purchase_order_status', create_type=False), server_default='PENDING', nullable=False),
    sa.Column('order_date', sa.Date(), nullable=False, comment='Fecha en que se emite la PO'),
    sa.Column('expected_date', sa.Date(), nullable=False, comment='Fecha esperada de recepción'),
    sa.Column('received_date', sa.Date(), nullable=True, comment='Fecha real de recepción completa o parcial'),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('shipping_cost', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('expected_date >= order_date', name='purchase_orders_expected_after_order'),
    sa.CheckConstraint('po_number = UPPER(po_number)', name='purchase_orders_number_upper'),
    sa.CheckConstraint('received_date IS NULL OR received_date >= order_date', name='purchase_orders_received_after_order'),
    sa.CheckConstraint('subtotal >= 0 AND shipping_cost >= 0 AND total >= 0', name='purchase_orders_amounts_nonnegative'),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('po_number')
    )
    op.create_index('ix_purchase_orders_destination', 'purchase_orders', ['destination_location_id'], unique=False)
    op.create_index('ix_purchase_orders_order_date', 'purchase_orders', ['order_date'], unique=False)
    op.create_index('ix_purchase_orders_status', 'purchase_orders', ['status'], unique=False)
    op.create_index('ix_purchase_orders_supplier', 'purchase_orders', ['supplier_id'], unique=False)

    # --- Tabla supplier_products -------------------------------------------
    op.create_table('supplier_products',
    sa.Column('supplier_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False, comment='Costo unitario congelado al momento de la asignación'),
    sa.Column('lead_time_days', sa.Integer(), nullable=False, comment='Lead time específico para este par (puede diferir del supplier)'),
    sa.Column('minimum_order_quantity', sa.Integer(), nullable=False, comment='MOQ específico para este par'),
    sa.Column('priority', sa.Integer(), nullable=False, comment='1 = preferido, 2 = alterno, 3 = respaldo'),
    sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('lead_time_days > 0', name='supplier_products_lead_time_positive'),
    sa.CheckConstraint('minimum_order_quantity > 0', name='supplier_products_moq_positive'),
    sa.CheckConstraint('priority IN (1, 2, 3)', name='supplier_products_priority_valid'),
    sa.CheckConstraint('unit_cost > 0', name='supplier_products_cost_positive'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('supplier_id', 'product_id', name='supplier_products_unique_supplier_product')
    )
    op.create_index('ix_supplier_products_priority', 'supplier_products', ['priority'], unique=False)
    op.create_index('ix_supplier_products_product', 'supplier_products', ['product_id'], unique=False)
    op.create_index('ix_supplier_products_supplier', 'supplier_products', ['supplier_id'], unique=False)

    # --- Tabla purchase_order_items ----------------------------------------
    op.create_table('purchase_order_items',
    sa.Column('purchase_order_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('quantity_ordered', sa.Integer(), nullable=False, comment='Cantidad solicitada al proveedor'),
    sa.Column('quantity_received', sa.Integer(), server_default='0', nullable=False, comment='Cantidad realmente recibida (puede ser < ordered)'),
    sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False, comment='Costo unitario congelado al momento de la PO'),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False, comment='quantity_ordered × unit_cost'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity_ordered > 0', name='po_items_ordered_positive'),
    sa.CheckConstraint('quantity_received <= quantity_ordered', name='po_items_received_lte_ordered'),
    sa.CheckConstraint('quantity_received >= 0', name='po_items_received_nonnegative'),
    sa.CheckConstraint('subtotal >= 0', name='po_items_subtotal_nonnegative'),
    sa.CheckConstraint('unit_cost > 0', name='po_items_unit_cost_positive'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('purchase_order_id', 'product_id', name='po_items_unique_po_product')
    )
    op.create_index('ix_po_items_po', 'purchase_order_items', ['purchase_order_id'], unique=False)
    op.create_index('ix_po_items_product', 'purchase_order_items', ['product_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_po_items_product', table_name='purchase_order_items')
    op.drop_index('ix_po_items_po', table_name='purchase_order_items')
    op.drop_table('purchase_order_items')
    op.drop_index('ix_supplier_products_supplier', table_name='supplier_products')
    op.drop_index('ix_supplier_products_product', table_name='supplier_products')
    op.drop_index('ix_supplier_products_priority', table_name='supplier_products')
    op.drop_table('supplier_products')
    op.drop_index('ix_purchase_orders_supplier', table_name='purchase_orders')
    op.drop_index('ix_purchase_orders_status', table_name='purchase_orders')
    op.drop_index('ix_purchase_orders_order_date', table_name='purchase_orders')
    op.drop_index('ix_purchase_orders_destination', table_name='purchase_orders')
    op.drop_table('purchase_orders')
    op.drop_index('ix_suppliers_type', table_name='suppliers')
    op.drop_index('ix_suppliers_status', table_name='suppliers')
    op.drop_index('ix_suppliers_state', table_name='suppliers')
    op.drop_table('suppliers')

    # --- Eliminar enums nuevos de M5 ---------------------------------------
    postgresql.ENUM(name='purchase_order_status').drop(op.get_bind())
    postgresql.ENUM(name='supplier_type').drop(op.get_bind())