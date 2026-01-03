"""Recreate posts table with canonical body fields

Revision ID: 202412101500
Revises: 202412081200
Create Date: 2024-12-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202412101500"
down_revision = "202412081200"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "posts" in inspector.get_table_names():
        op.drop_table("posts")

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
            server_onupdate=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_posts_slug", "posts", ["slug"], unique=True)
    op.create_index("ix_posts_status", "posts", ["status"], unique=False)
    op.create_index("ix_posts_published_at", "posts", ["published_at"], unique=False)
    op.create_index(
        "ix_posts_status_published_at", "posts", ["status", "published_at"], unique=False
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "posts" in inspector.get_table_names():
        op.drop_index("ix_posts_status_published_at", table_name="posts")
        op.drop_index("ix_posts_published_at", table_name="posts")
        op.drop_index("ix_posts_status", table_name="posts")
        op.drop_index("ix_posts_slug", table_name="posts")
        op.drop_table("posts")

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_raw", sa.Text(), nullable=True),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
            server_onupdate=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_posts_slug", "posts", ["slug"], unique=True)
    op.create_index("ix_posts_status", "posts", ["status"], unique=False)
    op.create_index("ix_posts_published_at", "posts", ["published_at"], unique=False)
    op.create_index(
        "ix_posts_status_published_at", "posts", ["status", "published_at"], unique=False
    )
