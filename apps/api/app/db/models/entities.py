from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Identity, Index
from sqlalchemy import Numeric, SmallInteger, String, Text, Time, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default=text("'Europe/London'"),
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    staff_branches: Mapped[list[StaffBranch]] = relationship(back_populates="branch")
    staff_schedules: Mapped[list[StaffSchedule]] = relationship(back_populates="branch")
    schedule_exceptions: Mapped[list[StaffScheduleException]] = relationship(
        back_populates="branch"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="branch")


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'doctor', 'marketer', 'operator')",
            name="ck_staff_role",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    can_take_chats: Mapped[bool | None] = mapped_column(server_default=text("FALSE"))
    can_take_appointments: Mapped[bool | None] = mapped_column(server_default=text("FALSE"))
    is_active: Mapped[bool | None] = mapped_column(server_default=text("TRUE"))
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
    )

    branches: Mapped[list[StaffBranch]] = relationship(back_populates="staff")
    schedules: Mapped[list[StaffSchedule]] = relationship(back_populates="staff")
    schedule_exceptions: Mapped[list[StaffScheduleException]] = relationship(
        back_populates="staff"
    )
    provided_appointments: Mapped[list[Appointment]] = relationship(
        back_populates="provider_staff",
        foreign_keys="Appointment.provider_staff_id",
    )
    operated_conversations: Mapped[list[Conversation]] = relationship(
        back_populates="operator",
        foreign_keys="Conversation.operator_id",
    )


class StaffBranch(Base):
    __tablename__ = "staff_branches"
    __table_args__ = (Index("idx_staff_branches_branch_id", "branch_id"),)

    staff_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool | None] = mapped_column(server_default=text("FALSE"))
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
    )

    staff: Mapped[Staff] = relationship(back_populates="branches")
    branch: Mapped[Branch] = relationship(back_populates="staff_branches")


class StaffSchedule(Base):
    __tablename__ = "staff_schedules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_staff_schedules_weekday"),
        CheckConstraint("end_time > start_time", name="ck_staff_schedules_time_range"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_staff_schedules_valid_range",
        ),
        Index("idx_staff_schedules_staff_weekday", "staff_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="SET NULL"),
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    staff: Mapped[Staff] = relationship(back_populates="schedules")
    branch: Mapped[Branch | None] = relationship(back_populates="staff_schedules")


class StaffScheduleException(Base):
    __tablename__ = "staff_schedule_exceptions"
    __table_args__ = (
        CheckConstraint(
            """
            (exception_type = 'day_off' AND start_time IS NULL AND end_time IS NULL)
            OR
            (exception_type IN ('custom_hours') AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)
            OR
            (exception_type IN ('vacation', 'sick_leave') AND start_time IS NULL AND end_time IS NULL)
            """,
            name="ck_staff_schedule_exceptions_type",
        ),
        Index("idx_staff_schedule_exceptions_staff_id", "staff_id"),
        Index("idx_staff_schedule_exceptions_exception_date", "exception_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="SET NULL"),
    )
    exception_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    staff: Mapped[Staff] = relationship(back_populates="schedule_exceptions")
    branch: Mapped[Branch | None] = relationship(back_populates="schedule_exceptions")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    source_contacts: Mapped[list[Contact]] = relationship(back_populates="source_channel")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="channel")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="channel")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_stage IN ('lead', 'qualified', 'booked', 'patient', 'inactive')",
            name="ck_contacts_lifecycle_stage",
        ),
        Index("idx_contacts_phone", "phone"),
        Index("idx_contacts_email", "email"),
        Index("idx_contacts_lifecycle_stage", "lifecycle_stage"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    birth_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    source_channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("channels.id", ondelete="SET NULL"),
    )
    lifecycle_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'lead'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    source_channel: Mapped[Channel | None] = relationship(back_populates="source_contacts")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="contact")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="contact")


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    services: Mapped[list[Service]] = relationship(back_populates="category")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_min > 0", name="ck_services_duration_min"),
        CheckConstraint("base_price >= 0", name="ck_services_base_price"),
        Index("idx_services_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("service_categories.id", ondelete="SET NULL"),
    )
    description: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    category: Mapped[ServiceCategory | None] = relationship(back_populates="services")
    appointment_services: Mapped[list[AppointmentService]] = relationship(
        back_populates="service"
    )


class AppointmentStatus(Base):
    __tablename__ = "appointment_statuses"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    appointments: Mapped[list[Appointment]] = relationship(back_populates="status")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_appointments_time_range"),
        Index("idx_appointments_contact_id", "contact_id"),
        Index("idx_appointments_provider_staff_id", "provider_staff_id"),
        Index("idx_appointments_branch_id", "branch_id"),
        Index("idx_appointments_status_id", "status_id"),
        Index("idx_appointments_start_at", "start_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_staff_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff.id", ondelete="SET NULL"),
    )
    branch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="SET NULL"),
    )
    start_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("appointment_statuses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("channels.id", ondelete="SET NULL"),
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    contact: Mapped[Contact] = relationship(back_populates="appointments")
    provider_staff: Mapped[Staff | None] = relationship(
        back_populates="provided_appointments",
        foreign_keys=[provider_staff_id],
    )
    branch: Mapped[Branch | None] = relationship(back_populates="appointments")
    status: Mapped[AppointmentStatus] = relationship(back_populates="appointments")
    channel: Mapped[Channel | None] = relationship(back_populates="appointments")
    services: Mapped[list[AppointmentService]] = relationship(
        back_populates="appointment"
    )


class AppointmentService(Base):
    __tablename__ = "appointment_services"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_appointment_services_quantity"),
        CheckConstraint("price >= 0", name="ck_appointment_services_price"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    appointment: Mapped[Appointment] = relationship(back_populates="services")
    service: Mapped[Service] = relationship(back_populates="appointment_services")


class ConversationStatus(Base):
    __tablename__ = "conversation_statuses"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    conversations: Mapped[list[Conversation]] = relationship(back_populates="status")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "handoff_status IN ('none', 'requested', 'assigned', 'in_progress', 'resolved')",
            name="ck_conversations_handoff_status",
        ),
        Index("idx_conversations_contact_id", "contact_id"),
        Index("idx_conversations_channel_id", "channel_id"),
        Index("idx_conversations_status_id", "status_id"),
        Index("idx_conversations_operator_id", "operator_id"),
        Index("idx_conversations_external_chat_id", "external_chat_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contacts.id", ondelete="SET NULL"),
    )
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("channels.id", ondelete="SET NULL"),
    )
    external_chat_id: Mapped[str | None] = mapped_column(String(255))
    status_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("conversation_statuses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    operator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("staff.id", ondelete="SET NULL"),
    )
    handoff_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'none'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    contact: Mapped[Contact | None] = relationship(back_populates="conversations")
    channel: Mapped[Channel | None] = relationship(back_populates="conversations")
    status: Mapped[ConversationStatus] = relationship(back_populates="conversations")
    operator: Mapped[Staff | None] = relationship(
        back_populates="operated_conversations",
        foreign_keys=[operator_id],
    )
    messages: Mapped[list[Message]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_messages_direction",
        ),
        CheckConstraint(
            "sender_type IN ('contact', 'bot', 'ai_assistant', 'staff', 'system', 'integration')",
            name="ck_messages_sender_type",
        ),
        CheckConstraint(
            "message_type IN ('text', 'image', 'file', 'audio')",
            name="ck_messages_message_type",
        ),
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_sent_at", "sent_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'text'"),
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
