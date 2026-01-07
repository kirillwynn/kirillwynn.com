"""merge heads: 202601042200 + 202601082000

Revision ID: 202601082100
Revises: 202601042200, 202601082000
Create Date: 2026-01-08

This is a merge migration that resolves multiple Alembic heads.
It performs no schema changes.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "202601082100"
down_revision = ("202601042200", "202601082000")
branch_labels = None
depends_on = None


def upgrade():
    # No-op merge revision.
    pass


def downgrade():
    # Downgrading a merge revision is a no-op as well.
    pass
