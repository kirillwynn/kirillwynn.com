"""add users table

Revision ID: 202410261200
Revises: 69e71e4d5e18
Create Date: 2024-10-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202410261200'
down_revision = '69e71e4d5e18'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
