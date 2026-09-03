"""user places, admin settings, alert events

Revision ID: b7c2d1e0f3a4
Revises: 17186652a814
Create Date: 2026-09-03 18:10:00+09:00
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = 'b7c2d1e0f3a4'
down_revision = '17186652a814'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('user_places',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('label', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lng', sa.Float(), nullable=False),
    sa.Column('sort', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_places_user_id'), 'user_places', ['user_id'], unique=False)
    op.create_table('admin_settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('alert_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('rule', sa.String(length=32), nullable=False),
    sa.Column('level', sa.String(length=8), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('threshold', sa.Float(), nullable=True),
    sa.Column('sent', sa.Boolean(), nullable=False),
    sa.Column('http_status', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=300), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_events_created_at'), 'alert_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_alert_events_rule'), 'alert_events', ['rule'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alert_events_rule'), table_name='alert_events')
    op.drop_index(op.f('ix_alert_events_created_at'), table_name='alert_events')
    op.drop_table('alert_events')
    op.drop_table('admin_settings')
    op.drop_index(op.f('ix_user_places_user_id'), table_name='user_places')
    op.drop_table('user_places')
