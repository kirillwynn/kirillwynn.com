"""recreate posts table to align with new model

Revision ID: 202412011000
Revises: 202411301200
Create Date: 2024-12-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202412011000'
down_revision = '202411301200'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('posts')

    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_raw', sa.Text(), nullable=True),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('tags', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), server_onupdate=sa.func.now()),
        sa.Column('published_at', sa.DateTime(), nullable=True),
    )

    op.create_index('ix_posts_slug', 'posts', ['slug'], unique=True)
    op.create_index('ix_posts_status', 'posts', ['status'], unique=False)
    op.create_index('ix_posts_published_at', 'posts', ['published_at'], unique=False)
    op.create_index('ix_posts_status_published_at', 'posts', ['status', 'published_at'], unique=False)


def downgrade():
    op.drop_index('ix_posts_status_published_at', table_name='posts')
    op.drop_index('ix_posts_published_at', table_name='posts')
    op.drop_index('ix_posts_status', table_name='posts')
    op.drop_index('ix_posts_slug', table_name='posts')
    op.drop_table('posts')
