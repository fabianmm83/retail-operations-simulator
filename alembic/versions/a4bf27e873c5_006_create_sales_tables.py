"""006 create sales tables

Revision ID: a4bf27e873c5
Revises: b3e3c09db3a4
Create Date: 2026-10-06 20:34:30.018684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a4bf27e873c5'
down_revision: Union[str, Sequence[str], None] = 'b3e3c09db3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- Crear enums nuevos de M6 (no existen todavía) ---------------------
    postgresql.ENUM(
        'NATIONAL', 'NORTH', 'CENTER', 'SOUTH',
        name='carrier_coverage',
    ).create(op.get_bind())

    postgresql.ENUM(
        'ONLINE', 'STORE',
        name='order_channel',
    ).create(op.get_bind())

    postgresql.ENUM(
        'PENDING', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED',
        'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'RETURNED',
        name='order_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'CARD', 'CASH', 'TRANSFER', 'OXXO', 'WALLET',
        name='payment_method',
    ).create(op.get_bind())

    postgresql.ENUM(
        'PENDING', 'PACKED', 'SHIPPED', 'IN_TRANSIT',
        'OUT_FOR_DELIVERY', 'DELIVERED', 'DELAYED', 'LOST',
        name='shipment_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'REQUESTED', 'APPROVED', 'RECEIVED', 'REFUNDED', 'REJECTED',
        name='return_status',
    ).create(op.get_bind())

    postgresql.ENUM(
        'WRONG_SIZE', 'NOT_AS_EXPECTED', 'DEFECTIVE',
        'LATE_DELIVERY', 'CHANGED_MIND', 'OTHER',
        name='return_reason',
    ).create(op.get_bind())

    postgresql.ENUM(
        'GOOD', 'DAMAGED', 'USED',
        name='return_item_condition',
    ).create(op.get_bind())

    # --- Tabla carriers ----------------------------------------------------
    op.create_table('carriers',
    sa.Column('carrier_code', sa.String(length=20), nullable=False, comment='Código de negocio: CAR-01 ... CAR-05'),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('coverage', postgresql.ENUM('NATIONAL', 'NORTH', 'CENTER', 'SOUTH', name='carrier_coverage', create_type=False), nullable=False),
    sa.Column('base_lead_time_days', sa.Integer(), nullable=False, comment='Lead time base en días (mínimo)'),
    sa.Column('max_lead_time_days', sa.Integer(), nullable=False, comment='Lead time máximo en días'),
    sa.Column('reliability', sa.Numeric(precision=5, scale=4), nullable=False, comment='Confiabilidad (0.0000–1.0000)'),
    sa.Column('base_cost', sa.Numeric(precision=10, scale=2), nullable=False, comment='Tarifa base en MXN'),
    sa.Column('cost_multiplier', sa.Numeric(precision=5, scale=4), server_default='1.0', nullable=False, comment='Multiplicador de costo relativo (1.0 = base)'),
    sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='record_status', create_type=False), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('base_cost >= 0', name='carriers_base_cost_nonnegative'),
    sa.CheckConstraint('base_lead_time_days > 0', name='carriers_base_lead_time_positive'),
    sa.CheckConstraint('carrier_code = UPPER(carrier_code)', name='carriers_code_upper'),
    sa.CheckConstraint('cost_multiplier > 0', name='carriers_cost_multiplier_positive'),
    sa.CheckConstraint('max_lead_time_days >= base_lead_time_days', name='carriers_max_lead_gte_base'),
    sa.CheckConstraint('reliability >= 0.5 AND reliability <= 1.0', name='carriers_reliability_range'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('carrier_code')
    )
    op.create_index('ix_carriers_coverage', 'carriers', ['coverage'], unique=False)
    op.create_index('ix_carriers_status', 'carriers', ['status'], unique=False)

    # --- Tabla orders ------------------------------------------------------
    op.create_table('orders',
    sa.Column('order_number', sa.String(length=30), nullable=False, comment='Código de negocio: ORD-2026-000001'),
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('state_id', sa.UUID(), nullable=False, comment='Estado del cliente al momento de la orden'),
    sa.Column('location_id', sa.UUID(), nullable=False, comment='Ubicación que surte la orden (CEDIS o tienda)'),
    sa.Column('channel', postgresql.ENUM('ONLINE', 'STORE', name='order_channel', create_type=False), nullable=False),
    sa.Column('status', postgresql.ENUM('PENDING', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'RETURNED', name='order_status', create_type=False), server_default='PENDING', nullable=False),
    sa.Column('order_date', sa.Date(), nullable=False, comment='Fecha simulada de la orden'),
    sa.Column('payment_method', postgresql.ENUM('CARD', 'CASH', 'TRANSFER', 'OXXO', 'WALLET', name='payment_method', create_type=False), nullable=False),
    sa.Column('paid', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('discount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('shipping_cost', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('discount <= subtotal', name='orders_discount_lte_subtotal'),
    sa.CheckConstraint('order_number = UPPER(order_number)', name='orders_number_upper'),
    sa.CheckConstraint('subtotal >= 0 AND discount >= 0 AND shipping_cost >= 0 AND total >= 0', name='orders_amounts_nonnegative'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_number')
    )
    op.create_index('ix_orders_channel', 'orders', ['channel'], unique=False)
    op.create_index('ix_orders_customer', 'orders', ['customer_id'], unique=False)
    op.create_index('ix_orders_date', 'orders', ['order_date'], unique=False)
    op.create_index('ix_orders_location', 'orders', ['location_id'], unique=False)
    op.create_index('ix_orders_state', 'orders', ['state_id'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)

    # --- Tabla order_items -------------------------------------------------
    op.create_table('order_items',
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('variant_id', sa.UUID(), nullable=False, comment='SKU específico vendido'),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Precio al momento de la venta (congelado)'),
    sa.Column('discount', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False, comment='quantity × unit_price - discount'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('discount >= 0', name='order_items_discount_nonnegative'),
    sa.CheckConstraint('quantity > 0', name='order_items_quantity_positive'),
    sa.CheckConstraint('subtotal >= 0', name='order_items_subtotal_nonnegative'),
    sa.CheckConstraint('unit_price >= 0', name='order_items_unit_price_nonnegative'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_order_items_order', 'order_items', ['order_id'], unique=False)
    op.create_index('ix_order_items_variant', 'order_items', ['variant_id'], unique=False)

    # --- Tabla returns -----------------------------------------------------
    op.create_table('returns',
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('status', postgresql.ENUM('REQUESTED', 'APPROVED', 'RECEIVED', 'REFUNDED', 'REJECTED', name='return_status', create_type=False), server_default='REQUESTED', nullable=False),
    sa.Column('reason', postgresql.ENUM('WRONG_SIZE', 'NOT_AS_EXPECTED', 'DEFECTIVE', 'LATE_DELIVERY', 'CHANGED_MIND', 'OTHER', name='return_reason', create_type=False), nullable=False),
    sa.Column('return_date', sa.Date(), nullable=False, comment='Fecha en que el cliente solicita la devolución'),
    sa.Column('received_date', sa.Date(), nullable=True, comment='Fecha en que se recibe el producto devuelto'),
    sa.Column('refund_date', sa.Date(), nullable=True, comment='Fecha en que se procesa el reembolso'),
    sa.Column('refund_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('received_date IS NULL OR received_date >= return_date', name='returns_received_after_request'),
    sa.CheckConstraint('refund_amount >= 0', name='returns_refund_nonnegative'),
    sa.CheckConstraint('refund_date IS NULL OR received_date IS NULL OR refund_date >= received_date', name='returns_refund_after_received'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_returns_customer', 'returns', ['customer_id'], unique=False)
    op.create_index('ix_returns_date', 'returns', ['return_date'], unique=False)
    op.create_index('ix_returns_order', 'returns', ['order_id'], unique=False)
    op.create_index('ix_returns_status', 'returns', ['status'], unique=False)

    # --- Tabla shipments ---------------------------------------------------
    op.create_table('shipments',
    sa.Column('shipment_number', sa.String(length=30), nullable=False, comment='Código de negocio: SHP-2026-000001'),
    sa.Column('tracking_number', sa.String(length=50), nullable=False, comment='Número de rastreo simulado'),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('carrier_id', sa.UUID(), nullable=False),
    sa.Column('origin_location_id', sa.UUID(), nullable=False, comment='CEDIS o tienda que despacha'),
    sa.Column('status', postgresql.ENUM('PENDING', 'PACKED', 'SHIPPED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'DELAYED', 'LOST', name='shipment_status', create_type=False), server_default='PENDING', nullable=False),
    sa.Column('shipped_at', sa.Date(), nullable=True, comment='Fecha de salida del origen'),
    sa.Column('estimated_delivery', sa.Date(), nullable=True, comment='Fecha estimada de entrega'),
    sa.Column('delivered_at', sa.Date(), nullable=True, comment='Fecha real de entrega'),
    sa.Column('shipping_cost', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
    sa.Column('weight_kg', sa.Numeric(precision=8, scale=3), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('delivered_at IS NULL OR shipped_at IS NULL OR delivered_at >= shipped_at', name='shipments_delivered_after_shipped'),
    sa.CheckConstraint('shipment_number = UPPER(shipment_number)', name='shipments_number_upper'),
    sa.CheckConstraint('shipped_at IS NULL OR estimated_delivery IS NULL OR estimated_delivery >= shipped_at', name='shipments_estimated_after_shipped'),
    sa.CheckConstraint('shipping_cost >= 0', name='shipments_cost_nonnegative'),
    sa.CheckConstraint('weight_kg >= 0', name='shipments_weight_nonnegative'),
    sa.ForeignKeyConstraint(['carrier_id'], ['carriers.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['origin_location_id'], ['locations.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('shipment_number')
    )
    op.create_index('ix_shipments_carrier', 'shipments', ['carrier_id'], unique=False)
    op.create_index('ix_shipments_order', 'shipments', ['order_id'], unique=False)
    op.create_index('ix_shipments_origin', 'shipments', ['origin_location_id'], unique=False)
    op.create_index('ix_shipments_shipped_at', 'shipments', ['shipped_at'], unique=False)
    op.create_index('ix_shipments_status', 'shipments', ['status'], unique=False)

    # --- Tabla return_items ------------------------------------------------
    op.create_table('return_items',
    sa.Column('return_id', sa.UUID(), nullable=False),
    sa.Column('order_item_id', sa.UUID(), nullable=False, comment='Item específico que se devuelve'),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('condition', postgresql.ENUM('GOOD', 'DAMAGED', 'USED', name='return_item_condition', create_type=False), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity > 0', name='return_items_quantity_positive'),
    sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['return_id'], ['returns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_return_items_order_item', 'return_items', ['order_item_id'], unique=False)
    op.create_index('ix_return_items_return', 'return_items', ['return_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_return_items_return', table_name='return_items')
    op.drop_index('ix_return_items_order_item', table_name='return_items')
    op.drop_table('return_items')
    op.drop_index('ix_shipments_status', table_name='shipments')
    op.drop_index('ix_shipments_shipped_at', table_name='shipments')
    op.drop_index('ix_shipments_origin', table_name='shipments')
    op.drop_index('ix_shipments_order', table_name='shipments')
    op.drop_index('ix_shipments_carrier', table_name='shipments')
    op.drop_table('shipments')
    op.drop_index('ix_returns_status', table_name='returns')
    op.drop_index('ix_returns_order', table_name='returns')
    op.drop_index('ix_returns_date', table_name='returns')
    op.drop_index('ix_returns_customer', table_name='returns')
    op.drop_table('returns')
    op.drop_index('ix_order_items_variant', table_name='order_items')
    op.drop_index('ix_order_items_order', table_name='order_items')
    op.drop_table('order_items')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_state', table_name='orders')
    op.drop_index('ix_orders_location', table_name='orders')
    op.drop_index('ix_orders_date', table_name='orders')
    op.drop_index('ix_orders_customer', table_name='orders')
    op.drop_index('ix_orders_channel', table_name='orders')
    op.drop_table('orders')
    op.drop_index('ix_carriers_status', table_name='carriers')
    op.drop_index('ix_carriers_coverage', table_name='carriers')
    op.drop_table('carriers')

    # --- Eliminar enums nuevos de M6 ---------------------------------------
    postgresql.ENUM(name='return_item_condition').drop(op.get_bind())
    postgresql.ENUM(name='return_reason').drop(op.get_bind())
    postgresql.ENUM(name='return_status').drop(op.get_bind())
    postgresql.ENUM(name='shipment_status').drop(op.get_bind())
    postgresql.ENUM(name='payment_method').drop(op.get_bind())
    postgresql.ENUM(name='order_status').drop(op.get_bind())
    postgresql.ENUM(name='order_channel').drop(op.get_bind())
    postgresql.ENUM(name='carrier_coverage').drop(op.get_bind())