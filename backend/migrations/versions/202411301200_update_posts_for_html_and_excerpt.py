"""update posts for html and excerpt

Revision ID: 202411301200
Revises: 202411081200
Create Date: 2024-11-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202411301200'
down_revision = '202411081200'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('posts', sa.Column('body_html', sa.Text(), nullable=False, server_default=''))
    op.add_column('posts', sa.Column('body_raw', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('excerpt', sa.Text(), nullable=True))

    op.create_index('ix_posts_status', 'posts', ['status'], unique=False)
    op.create_index('ix_posts_published_at', 'posts', ['published_at'], unique=False)
    op.create_index('ix_posts_status_published_at', 'posts', ['status', 'published_at'], unique=False)

    op.execute("UPDATE posts SET body_html = body_md WHERE body_html = '' OR body_html IS NULL")
    op.execute("UPDATE posts SET body_raw = body_md WHERE body_md IS NOT NULL AND body_raw IS NULL")
    op.execute("UPDATE posts SET excerpt = SUBSTRING(COALESCE(body_md, '') FROM 1 FOR 200) WHERE excerpt IS NULL")

    op.alter_column('posts', 'body_html', server_default=None)

    op.drop_column('posts', 'body_md')


def downgrade():
    op.add_column('posts', sa.Column('body_md', sa.Text(), nullable=False, server_default=''))

    op.execute("UPDATE posts SET body_md = body_html WHERE body_md = ''")

    op.drop_index('ix_posts_status_published_at', table_name='posts')
    op.drop_index('ix_posts_published_at', table_name='posts')
    op.drop_index('ix_posts_status', table_name='posts')

    op.drop_column('posts', 'excerpt')
    op.drop_column('posts', 'body_raw')
    op.drop_column('posts', 'body_html')

    op.alter_column('posts', 'body_md', server_default=None)
