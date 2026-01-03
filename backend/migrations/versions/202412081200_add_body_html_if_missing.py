"""Ensure posts.body_html exists and is populated

Revision ID: 202412081200
Revises: 202412041200
Create Date: 2024-12-08 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "202412081200"
down_revision = "202412041200"
branch_labels = None
depends_on = None


def _table_has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "posts" not in inspector.get_table_names():
        return

    has_body_md = _table_has_column(inspector, "posts", "body_md")
    has_body_html = _table_has_column(inspector, "posts", "body_html")

    if not has_body_md:
        op.add_column("posts", sa.Column("body_md", sa.Text(), nullable=True))
        has_body_md = True

    if not has_body_html:
        op.add_column(
            "posts",
            sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        )
        has_body_html = True

    if has_body_md and has_body_html:
        op.execute(
            sa.text(
                """
                UPDATE posts
                SET body_html = body_md
                WHERE (body_html IS NULL OR body_html = '') AND body_md IS NOT NULL
                """
            )
        )

    op.execute(sa.text("UPDATE posts SET body_html = '' WHERE body_html IS NULL"))

    op.alter_column(
        "posts",
        "body_html",
        existing_type=sa.Text(),
        nullable=False,
        server_default="",
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "posts" not in inspector.get_table_names():
        return

    if _table_has_column(inspector, "posts", "body_html"):
        op.drop_column("posts", "body_html")

