"""Add contact channel identities table.

Revision ID: 20260323_0004
Revises: 20260322_0003
Create Date: 2026-03-23 11:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260323_0004"
down_revision: str | None = "20260322_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_channel_identities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "channel_id",
            "external_id",
            name="uq_contact_channel_identities_channel_external_id",
        ),
    )
    op.create_index(
        "idx_contact_channel_identities_contact_id",
        "contact_channel_identities",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "idx_contact_channel_identities_channel_id",
        "contact_channel_identities",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "idx_contact_channel_identities_external_id",
        "contact_channel_identities",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        "idx_contact_channel_identities_phone",
        "contact_channel_identities",
        ["phone"],
        unique=False,
    )
    op.create_index(
        "idx_contact_channel_identities_email",
        "contact_channel_identities",
        ["email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_contact_channel_identities_email",
        table_name="contact_channel_identities",
    )
    op.drop_index(
        "idx_contact_channel_identities_phone",
        table_name="contact_channel_identities",
    )
    op.drop_index(
        "idx_contact_channel_identities_external_id",
        table_name="contact_channel_identities",
    )
    op.drop_index(
        "idx_contact_channel_identities_channel_id",
        table_name="contact_channel_identities",
    )
    op.drop_index(
        "idx_contact_channel_identities_contact_id",
        table_name="contact_channel_identities",
    )
    op.drop_table("contact_channel_identities")
