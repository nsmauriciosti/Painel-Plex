"""Add tickets table

Revision ID: c92625823728
Revises: w9s4e5a8f6j2
Create Date: 2026-04-26 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c92625823728'
down_revision = 'w9s4e5a8f6j2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_plex_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('media_title', sa.String(), nullable=True),
        sa.Column('issue_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_plex_id'], ['user_profiles.plex_user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_index(op.f('ix_tickets_user_plex_id'), 'tickets', ['user_plex_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tickets_user_plex_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_table('tickets')
