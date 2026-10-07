"""003 create customers tables

Revision ID: 36f36181cb96
Revises: 797d1297f7a7
Create Date: 2026-10-06 19:34:58.017215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '36f36181cb96'
down_revision: Union[str, Sequence[str], None] = '797d1297f7a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- Crear enums nuevos de M3 (no existen todavía) ---------------------
    postgresql.ENUM(
        'MALE', 'FEMALE', 'OTHER',
        name='gender_type',
    ).create(op.get_bind())

    postgresql.ENUM(
        'NEW', 'ONE_TIME', 'OCCASIONAL', 'REGULAR', 'LOYAL', 'INACTIVE',
        name='customer_profile',
    ).create(op.get_bind())

    postgresql.ENUM(
        'ONLINE', 'STORE', 'OMNICHANNEL',
        name='channel_preference',
    ).create(op.get_bind())

    postgresql.ENUM(
        'LOW', 'MEDIUM', 'HIGH',
        name='price_sensitivity',
    ).create(op.get_bind())

    # --- Tabla customers ---------------------------------------------------
    op.create_table('customers',
    sa.Column('customer_code', sa.String(length=20), nullable=False, comment='Código de negocio: CUST-000001'),
    sa.Column('first_name', sa.String(length=100), nullable=False),
    sa.Column('last_name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False, comment='Formato: +52XXXXXXXXXX'),
    sa.Column('birth_date', sa.Date(), nullable=False),
    sa.Column('gender', postgresql.ENUM('MALE', 'FEMALE', 'OTHER', name='gender_type', create_type=False), nullable=False),
    sa.Column('state_id', sa.UUID(), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('postal_code', sa.String(length=10), nullable=False),
    sa.Column('profile', postgresql.ENUM('NEW', 'ONE_TIME', 'OCCASIONAL', 'REGULAR', 'LOYAL', 'INACTIVE', name='customer_profile', create_type=False), server_default='NEW', nullable=False),
    sa.Column('channel_preference', postgresql.ENUM('ONLINE', 'STORE', 'OMNICHANNEL', name='channel_preference', create_type=False), nullable=False),
    sa.Column('preferred_segment', postgresql.ENUM('WOMEN', 'MEN', 'KIDS', 'UNISEX', name='segment_type', create_type=False), nullable=False),
    sa.Column('price_sensitivity', postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='price_sensitivity', create_type=False), nullable=False),
    sa.Column('signup_date', sa.Date(), nullable=False),
    sa.Column('first_order_date', sa.Date(), nullable=True),
    sa.Column('last_order_date', sa.Date(), nullable=True),
    sa.Column('total_orders', sa.Integer(), server_default='0', nullable=False),
    sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('total_units', sa.Integer(), server_default='0', nullable=False),
    sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='record_status', create_type=False), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(profile = 'NEW' AND total_orders = 0) OR (profile <> 'NEW')", name='customers_new_profile_no_orders'),
    sa.CheckConstraint('customer_code = UPPER(customer_code)', name='customers_code_upper'),
    sa.CheckConstraint('first_order_date IS NULL OR first_order_date >= signup_date', name='customers_first_order_after_signup'),
    sa.CheckConstraint('last_order_date IS NULL OR last_order_date >= first_order_date', name='customers_last_order_after_first'),
    sa.CheckConstraint('total_orders >= 0', name='customers_total_orders_nonnegative'),
    sa.CheckConstraint('total_revenue >= 0', name='customers_total_revenue_nonnegative'),
    sa.CheckConstraint('total_units >= 0', name='customers_total_units_nonnegative'),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_code'),
    sa.UniqueConstraint('email')
    )
    op.create_index('ix_customers_channel', 'customers', ['channel_preference'], unique=False)
    op.create_index('ix_customers_price_sensitivity', 'customers', ['price_sensitivity'], unique=False)
    op.create_index('ix_customers_profile', 'customers', ['profile'], unique=False)
    op.create_index('ix_customers_segment', 'customers', ['preferred_segment'], unique=False)
    op.create_index('ix_customers_state', 'customers', ['state_id'], unique=False)
    op.create_index('ix_customers_status', 'customers', ['status'], unique=False)

    # --- Tabla customer_category_preference --------------------------------
    op.create_table('customer_category_preference',
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('category_id', sa.UUID(), nullable=False),
    sa.Column('preference_weight', sa.Numeric(precision=5, scale=4), server_default='1.0', nullable=False, comment='Peso relativo de la preferencia (1.0 = neutro)'),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('preference_weight > 0', name='preference_weight_positive'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_customer_pref_category', 'customer_category_preference', ['category_id'], unique=False)
    op.create_index('ix_customer_pref_customer', 'customer_category_preference', ['customer_id'], unique=False)
    op.create_index('ux_customer_pref_unique', 'customer_category_preference', ['customer_id', 'category_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_customer_pref_unique', table_name='customer_category_preference')
    op.drop_index('ix_customer_pref_customer', table_name='customer_category_preference')
    op.drop_index('ix_customer_pref_category', table_name='customer_category_preference')
    op.drop_table('customer_category_preference')
    op.drop_index('ix_customers_status', table_name='customers')
    op.drop_index('ix_customers_state', table_name='customers')
    op.drop_index('ix_customers_segment', table_name='customers')
    op.drop_index('ix_customers_profile', table_name='customers')
    op.drop_index('ix_customers_price_sensitivity', table_name='customers')
    op.drop_index('ix_customers_channel', table_name='customers')
    op.drop_table('customers')

    # --- Eliminar enums nuevos de M3 ---------------------------------------
    postgresql.ENUM(name='price_sensitivity').drop(op.get_bind())
    postgresql.ENUM(name='channel_preference').drop(op.get_bind())
    postgresql.ENUM(name='customer_profile').drop(op.get_bind())
    postgresql.ENUM(name='gender_type').drop(op.get_bind())