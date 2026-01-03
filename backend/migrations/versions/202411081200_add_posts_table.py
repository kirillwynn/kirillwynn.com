"""add posts table

Revision ID: 202411081200
Revises: 202410261200
Create Date: 2024-11-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202411081200'
down_revision = '202410261200'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('tags', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_posts_slug'), 'posts', ['slug'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_posts_slug'), table_name='posts')
    op.drop_table('posts')
