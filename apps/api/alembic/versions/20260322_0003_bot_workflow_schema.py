"""Add bot workflow support schema.

Revision ID: 20260322_0003
Revises: 20260314_0002
Create Date: 2026-03-22 16:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260322_0003"
down_revision: str | None = "20260314_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("parking_info", sa.Text(), nullable=True))
    op.add_column("branches", sa.Column("directions", sa.Text(), nullable=True))
    op.add_column("branches", sa.Column("map_url", sa.String(length=500), nullable=True))

    op.create_table(
        "branch_hours",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_branch_hours_weekday"),
        sa.CheckConstraint("close_time > open_time", name="ck_branch_hours_time_range"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_branch_hours_branch_weekday",
        "branch_hours",
        ["branch_id", "weekday"],
        unique=False,
    )

    op.create_table(
        "staff_services",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "staff_id",
            "service_id",
            "branch_id",
            name="uq_staff_services_staff_service_branch",
        ),
    )
    op.create_index(
        "idx_staff_services_staff_id", "staff_services", ["staff_id"], unique=False
    )
    op.create_index(
        "idx_staff_services_service_id", "staff_services", ["service_id"], unique=False
    )
    op.create_index(
        "idx_staff_services_branch_id", "staff_services", ["branch_id"], unique=False
    )

    op.add_column(
        "conversations",
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("is_spam", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_conversations_priority",
        "conversations",
        "priority IN ('low', 'normal', 'high', 'urgent')",
    )
    op.create_index(
        "idx_conversations_priority", "conversations", ["priority"], unique=False
    )

    op.create_table(
        "appointment_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("branch_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_service_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_provider_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("preferred_time", sa.Time(), nullable=True),
        sa.Column("time_range_notes", sa.String(length=100), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column(
            "urgency",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('new', 'collecting_data', 'pending_admin', 'slot_offered', 'converted', 'cancelled')",
            name="ck_appointment_requests_status",
        ),
        sa.CheckConstraint(
            "urgency IN ('normal', 'urgent')",
            name="ck_appointment_requests_urgency",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["requested_service_id"], ["services.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["requested_provider_staff_id"], ["staff.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_appointment_requests_contact_id",
        "appointment_requests",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        "idx_appointment_requests_conversation_id",
        "appointment_requests",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "idx_appointment_requests_status",
        "appointment_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_appointment_requests_preferred_date",
        "appointment_requests",
        ["preferred_date"],
        unique=False,
    )

    op.create_table(
        "conversation_intents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("intent_code", sa.String(length=100), nullable=False),
        sa.Column("route_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extracted_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "route_type IN ('auto_reply', 'auto_reply_and_collect', 'handoff_admin', 'handoff_urgent', 'silent_ignore')",
            name="ck_conversation_intents_route_type",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_conversation_intents_confidence",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_conversation_intents_conversation_id",
        "conversation_intents",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_intents_message_id",
        "conversation_intents",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_intents_intent_code",
        "conversation_intents",
        ["intent_code"],
        unique=False,
    )

    op.create_table(
        "handoff_tasks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=True),
        sa.Column("appointment_request_id", sa.BigInteger(), nullable=True),
        sa.Column("assigned_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "task_type IN ('admin_followup', 'urgent_case', 'document_request', 'callback_request', 'complaint', 'post_visit', 'manual_booking', 'manual_reschedule', 'manual_cancel')",
            name="ck_handoff_tasks_task_type",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="ck_handoff_tasks_priority",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'assigned', 'in_progress', 'completed', 'cancelled')",
            name="ck_handoff_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_request_id"], ["appointment_requests.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["assigned_staff_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_handoff_tasks_conversation_id", "handoff_tasks", ["conversation_id"], unique=False
    )
    op.create_index(
        "idx_handoff_tasks_assigned_staff_id",
        "handoff_tasks",
        ["assigned_staff_id"],
        unique=False,
    )
    op.create_index("idx_handoff_tasks_status", "handoff_tasks", ["status"], unique=False)
    op.create_index(
        "idx_handoff_tasks_priority", "handoff_tasks", ["priority"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_handoff_tasks_priority", table_name="handoff_tasks")
    op.drop_index("idx_handoff_tasks_status", table_name="handoff_tasks")
    op.drop_index("idx_handoff_tasks_assigned_staff_id", table_name="handoff_tasks")
    op.drop_index("idx_handoff_tasks_conversation_id", table_name="handoff_tasks")
    op.drop_table("handoff_tasks")

    op.drop_index(
        "idx_conversation_intents_intent_code", table_name="conversation_intents"
    )
    op.drop_index(
        "idx_conversation_intents_message_id", table_name="conversation_intents"
    )
    op.drop_index(
        "idx_conversation_intents_conversation_id", table_name="conversation_intents"
    )
    op.drop_table("conversation_intents")

    op.drop_index(
        "idx_appointment_requests_preferred_date", table_name="appointment_requests"
    )
    op.drop_index("idx_appointment_requests_status", table_name="appointment_requests")
    op.drop_index(
        "idx_appointment_requests_conversation_id", table_name="appointment_requests"
    )
    op.drop_index("idx_appointment_requests_contact_id", table_name="appointment_requests")
    op.drop_table("appointment_requests")

    op.drop_index("idx_conversations_priority", table_name="conversations")
    op.drop_constraint("ck_conversations_priority", "conversations", type_="check")
    op.drop_column("conversations", "is_spam")
    op.drop_column("conversations", "priority")

    op.drop_index("idx_staff_services_branch_id", table_name="staff_services")
    op.drop_index("idx_staff_services_service_id", table_name="staff_services")
    op.drop_index("idx_staff_services_staff_id", table_name="staff_services")
    op.drop_table("staff_services")

    op.drop_index("idx_branch_hours_branch_weekday", table_name="branch_hours")
    op.drop_table("branch_hours")

    op.drop_column("branches", "map_url")
    op.drop_column("branches", "directions")
    op.drop_column("branches", "parking_info")
