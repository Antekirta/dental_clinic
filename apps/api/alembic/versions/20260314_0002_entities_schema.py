"""Create core clinic entities schema.

Revision ID: 20260314_0002
Revises: 20260313_0001
Create Date: 2026-03-14 10:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260314_0002"
down_revision: str | None = "20260313_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=100),
            nullable=False,
            server_default=sa.text("'Europe/London'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "staff",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("can_take_chats", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column(
            "can_take_appointments",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'doctor', 'marketer', 'operator')",
            name="ck_staff_role",
        ),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("code", name="uq_channels_code"),
        sa.UniqueConstraint("display_name", name="uq_channels_display_name"),
    )

    op.create_table(
        "service_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("name", name="uq_service_categories_name"),
    )

    op.create_table(
        "appointment_statuses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("code", name="uq_appointment_statuses_code"),
        sa.UniqueConstraint("name", name="uq_appointment_statuses_name"),
    )

    op.create_table(
        "conversation_statuses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("code", name="uq_conversation_statuses_code"),
        sa.UniqueConstraint("name", name="uq_conversation_statuses_name"),
    )

    op.create_table(
        "staff_branches",
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("staff_id", "branch_id"),
    )

    op.create_table(
        "staff_schedules",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=True),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("end_time > start_time", name="ck_staff_schedules_time_range"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_staff_schedules_weekday"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_staff_schedules_valid_range",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "staff_schedule_exceptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("staff_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=True),
        sa.Column("exception_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("exception_type", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            """
            (exception_type = 'day_off' AND start_time IS NULL AND end_time IS NULL)
            OR
            (exception_type IN ('custom_hours') AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)
            OR
            (exception_type IN ('vacation', 'sick_leave') AND start_time IS NULL AND end_time IS NULL)
            """,
            name="ck_staff_schedule_exceptions_type",
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_channel_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "lifecycle_stage",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'lead'"),
        ),
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
            "lifecycle_stage IN ('lead', 'qualified', 'booked', 'patient', 'inactive')",
            name="ck_contacts_lifecycle_stage",
        ),
        sa.ForeignKeyConstraint(["source_channel_id"], ["channels.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.CheckConstraint("base_price >= 0", name="ck_services_base_price"),
        sa.CheckConstraint("duration_min > 0", name="ck_services_duration_min"),
        sa.ForeignKeyConstraint(["category_id"], ["service_categories.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_staff_id", sa.BigInteger(), nullable=True),
        sa.Column("branch_id", sa.BigInteger(), nullable=True),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
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
        sa.CheckConstraint("end_at > start_at", name="ck_appointments_time_range"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["provider_staff_id"], ["staff.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["status_id"], ["appointment_statuses.id"], ondelete="RESTRICT"
        ),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("contact_id", sa.BigInteger(), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("external_chat_id", sa.String(length=255), nullable=True),
        sa.Column("status_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "handoff_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
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
            "handoff_status IN ('none', 'requested', 'assigned', 'in_progress', 'resolved')",
            name="ck_conversations_handoff_status",
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operator_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["status_id"], ["conversation_statuses.id"], ondelete="RESTRICT"
        ),
    )

    op.create_table(
        "appointment_services",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("appointment_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_appointment_services_price"),
        sa.CheckConstraint("quantity > 0", name="ck_appointment_services_quantity"),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("sender_type", sa.String(length=50), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column(
            "message_type",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'text'"),
        ),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_messages_direction",
        ),
        sa.CheckConstraint(
            "message_type IN ('text', 'image', 'file', 'audio')",
            name="ck_messages_message_type",
        ),
        sa.CheckConstraint(
            "sender_type IN ('contact', 'bot', 'ai_assistant', 'staff', 'system', 'integration')",
            name="ck_messages_sender_type",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
    )

    op.create_index(
        "idx_staff_branches_branch_id", "staff_branches", ["branch_id"], unique=False
    )
    op.create_index(
        "idx_staff_schedules_staff_weekday",
        "staff_schedules",
        ["staff_id", "weekday"],
        unique=False,
    )
    op.create_index(
        "idx_staff_schedule_exceptions_staff_id",
        "staff_schedule_exceptions",
        ["staff_id"],
        unique=False,
    )
    op.create_index(
        "idx_staff_schedule_exceptions_exception_date",
        "staff_schedule_exceptions",
        ["exception_date"],
        unique=False,
    )
    op.create_index("idx_contacts_phone", "contacts", ["phone"], unique=False)
    op.create_index("idx_contacts_email", "contacts", ["email"], unique=False)
    op.create_index(
        "idx_contacts_lifecycle_stage", "contacts", ["lifecycle_stage"], unique=False
    )
    op.create_index("idx_services_category_id", "services", ["category_id"], unique=False)
    op.create_index(
        "idx_appointments_contact_id", "appointments", ["contact_id"], unique=False
    )
    op.create_index(
        "idx_appointments_provider_staff_id",
        "appointments",
        ["provider_staff_id"],
        unique=False,
    )
    op.create_index(
        "idx_appointments_branch_id", "appointments", ["branch_id"], unique=False
    )
    op.create_index(
        "idx_appointments_status_id", "appointments", ["status_id"], unique=False
    )
    op.create_index(
        "idx_appointments_start_at", "appointments", ["start_at"], unique=False
    )
    op.create_index(
        "idx_conversations_contact_id", "conversations", ["contact_id"], unique=False
    )
    op.create_index(
        "idx_conversations_channel_id", "conversations", ["channel_id"], unique=False
    )
    op.create_index(
        "idx_conversations_status_id", "conversations", ["status_id"], unique=False
    )
    op.create_index(
        "idx_conversations_operator_id", "conversations", ["operator_id"], unique=False
    )
    op.create_index(
        "idx_conversations_external_chat_id",
        "conversations",
        ["external_chat_id"],
        unique=False,
    )
    op.create_index(
        "idx_messages_conversation_id", "messages", ["conversation_id"], unique=False
    )
    op.create_index("idx_messages_sent_at", "messages", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_messages_sent_at", table_name="messages")
    op.drop_index("idx_messages_conversation_id", table_name="messages")
    op.drop_index("idx_conversations_external_chat_id", table_name="conversations")
    op.drop_index("idx_conversations_operator_id", table_name="conversations")
    op.drop_index("idx_conversations_status_id", table_name="conversations")
    op.drop_index("idx_conversations_channel_id", table_name="conversations")
    op.drop_index("idx_conversations_contact_id", table_name="conversations")
    op.drop_index("idx_appointments_start_at", table_name="appointments")
    op.drop_index("idx_appointments_status_id", table_name="appointments")
    op.drop_index("idx_appointments_branch_id", table_name="appointments")
    op.drop_index("idx_appointments_provider_staff_id", table_name="appointments")
    op.drop_index("idx_appointments_contact_id", table_name="appointments")
    op.drop_index("idx_services_category_id", table_name="services")
    op.drop_index("idx_contacts_lifecycle_stage", table_name="contacts")
    op.drop_index("idx_contacts_email", table_name="contacts")
    op.drop_index("idx_contacts_phone", table_name="contacts")
    op.drop_index(
        "idx_staff_schedule_exceptions_exception_date",
        table_name="staff_schedule_exceptions",
    )
    op.drop_index(
        "idx_staff_schedule_exceptions_staff_id",
        table_name="staff_schedule_exceptions",
    )
    op.drop_index("idx_staff_schedules_staff_weekday", table_name="staff_schedules")
    op.drop_index("idx_staff_branches_branch_id", table_name="staff_branches")

    op.drop_table("messages")
    op.drop_table("appointment_services")
    op.drop_table("conversations")
    op.drop_table("appointments")
    op.drop_table("services")
    op.drop_table("contacts")
    op.drop_table("staff_schedule_exceptions")
    op.drop_table("staff_schedules")
    op.drop_table("staff_branches")
    op.drop_table("conversation_statuses")
    op.drop_table("appointment_statuses")
    op.drop_table("service_categories")
    op.drop_table("channels")
    op.drop_table("staff")
    op.drop_table("branches")
