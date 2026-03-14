"""Initial database baseline.

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 22:30:00
"""

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "20260313_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial migration baseline without schema objects."""


def downgrade() -> None:
    """Revert the initial migration baseline."""
