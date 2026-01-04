"""Add author_id to posts and backfill existing rows.

Revision ID: 202601041930
Revises: 202412101500
Create Date: 2026-01-04 20:55:00
"""

from alembic import op
import sqlalchemy as sa

revision = "202601041930"
down_revision = "202412101500"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Add author_id as nullable first to avoid breaking existing rows
    op.add_column("posts", sa.Column("author_id", sa.Integer(), nullable=True))

    # 2) Add FK + index (safe while nullable)
    op.create_foreign_key(
        "fk_posts_author_id_users",
        source_table="posts",
        referent_table="users",
        local_cols=["author_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])

    # 3) Backfill existing posts with an admin user (fail-fast if none exists)
    conn = op.get_bind()
    admin_id = conn.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true ORDER BY id ASC LIMIT 1")
    ).scalar()

    if admin_id is None:
        raise RuntimeError(
            "No admin user found to backfill posts.author_id. "
            "Create an admin user first (flask create-admin), then re-run."
        )

    conn.execute(
        sa.text("UPDATE posts SET author_id = :admin_id WHERE author_id IS NULL"),
        {"admin_id": admin_id},
    )

    # 4) Enforce NOT NULL after data is consistent
    op.alter_column("posts", "author_id", existing_type=sa.Integer(), nullable=False)


def downgrade():
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_constraint("fk_posts_author_id_users", "posts", type_="foreignkey")
    op.drop_column("posts", "author_id")
