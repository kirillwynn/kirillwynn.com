"""posts: add body_json column

Revision ID: 202601082000
Revises: 69e71e4d5e18
Create Date: 2026-01-08

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202601082000"
down_revision = "69e71e4d5e18"
branch_labels = None
depends_on = None


def upgrade():
    # Only add the new column. Do NOT touch unrelated indexes/constraints
    # that autogenerate may "detect" due to naming/metadata differences.
    op.add_column("posts", sa.Column("body_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("posts", "body_json")
