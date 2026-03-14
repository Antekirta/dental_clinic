from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from app.db.models import (
    Appointment,
    AppointmentService,
    AppointmentStatus,
    Branch,
    Channel,
    Contact,
    Conversation,
    ConversationStatus,
    Message,
    Service,
    ServiceCategory,
    Staff,
    StaffBranch,
    StaffSchedule,
    StaffScheduleException,
)
from app.db.session import SessionLocal


def get_by(session, model, **filters):
    return session.query(model).filter_by(**filters).one_or_none()


def upsert_reference_rows(session) -> dict[str, dict[str, object]]:
    channels = {}
    for code, display_name, notes in [
        ("instagram", "Instagram", "Inbound social channel"),
        ("telegram", "Telegram", "Messaging channel for patient support"),
        ("whatsapp", "WhatsApp", "Primary chat channel"),
        ("website", "Website", "Lead capture forms"),
        ("website_live_chat", "Website live chat", "Live chat widget on the clinic site"),
        ("phone", "Phone", "Direct call bookings"),
    ]:
        channel = get_by(session, Channel, code=code)
        if channel is None:
            channel = Channel(code=code)
            session.add(channel)
        channel.display_name = display_name
        channel.notes = notes
        channels[code] = channel

    service_categories = {}
    for name, notes in [
        ("General Dentistry", "Routine and restorative care"),
        ("Orthodontics", "Alignment and correction services"),
        ("Aesthetic Dentistry", "Cosmetic and whitening treatments"),
    ]:
        category = get_by(session, ServiceCategory, name=name)
        if category is None:
            category = ServiceCategory(name=name)
            session.add(category)
        category.notes = notes
        service_categories[name] = category

    appointment_statuses = {}
    for code, name, notes in [
        ("scheduled", "Scheduled", "Booked and awaiting attendance"),
        ("confirmed", "Confirmed", "Confirmed by patient"),
        ("completed", "Completed", "Visit finished"),
        ("cancelled", "Cancelled", "Cancelled before service"),
        ("no_show", "No Show", "Patient did not attend"),
    ]:
        status = get_by(session, AppointmentStatus, code=code)
        if status is None:
            status = AppointmentStatus(code=code)
            session.add(status)
        status.name = name
        status.notes = notes
        appointment_statuses[code] = status

    conversation_statuses = {}
    for code, name, notes in [
        ("open", "Open", "Conversation is active"),
        ("waiting_human", "Waiting Human", "Awaiting operator pickup"),
        ("closed", "Closed", "Conversation completed"),
    ]:
        status = get_by(session, ConversationStatus, code=code)
        if status is None:
            status = ConversationStatus(code=code)
            session.add(status)
        status.name = name
        status.notes = notes
        conversation_statuses[code] = status

    session.flush()
    return {
        "channels": channels,
        "service_categories": service_categories,
        "appointment_statuses": appointment_statuses,
        "conversation_statuses": conversation_statuses,
    }


def upsert_branches_and_staff(session) -> dict[str, object]:
    branches = {}
    for name, address, phone in [
        ("Marylebone Clinic", "221B Baker Street, Marylebone, London", "+44 20 7946 0100"),
        ("Canary Wharf Clinic", "14 Bank Street, Canary Wharf, London", "+44 20 7946 0200"),
    ]:
        branch = get_by(session, Branch, name=name)
        if branch is None:
            branch = Branch(name=name)
            session.add(branch)
        branch.address = address
        branch.phone = phone
        branch.timezone = "Europe/London"
        branch.is_active = True
        branches[name] = branch

    staff_members = {}
    for full_name, role, specialty, phone, email, can_take_chats, can_take_appointments in [
        (
            "Dr. Emily Carter",
            "doctor",
            "Orthodontics",
            "+44 7700 900101",
            "emily.carter@clinic.local",
            False,
            True,
        ),
        (
            "Dr. James Patel",
            "doctor",
            "General Dentistry",
            "+44 7700 900102",
            "james.patel@clinic.local",
            False,
            True,
        ),
        (
            "Olivia Bennett",
            "operator",
            None,
            "+44 7700 900201",
            "olivia.bennett@clinic.local",
            True,
            False,
        ),
        (
            "Thomas Green",
            "marketer",
            None,
            "+44 7700 900301",
            "thomas.green@clinic.local",
            False,
            False,
        ),
    ]:
        staff = get_by(session, Staff, email=email)
        if staff is None:
            staff = Staff(email=email)
            session.add(staff)
        staff.full_name = full_name
        staff.role = role
        staff.specialty = specialty
        staff.phone = phone
        staff.can_take_chats = can_take_chats
        staff.can_take_appointments = can_take_appointments
        staff.is_active = True
        staff_members[email] = staff

    session.flush()

    for staff_email, branch_name, is_primary in [
        ("emily.carter@clinic.local", "Marylebone Clinic", True),
        ("james.patel@clinic.local", "Canary Wharf Clinic", True),
        ("olivia.bennett@clinic.local", "Marylebone Clinic", True),
        ("olivia.bennett@clinic.local", "Canary Wharf Clinic", False),
        ("thomas.green@clinic.local", "Marylebone Clinic", True),
    ]:
        link = (
            session.query(StaffBranch)
            .filter_by(
                staff_id=staff_members[staff_email].id,
                branch_id=branches[branch_name].id,
            )
            .one_or_none()
        )
        if link is None:
            link = StaffBranch(
                staff=staff_members[staff_email],
                branch=branches[branch_name],
            )
            session.add(link)
        link.is_primary = is_primary

    for staff_email, branch_name, weekday, start_time, end_time in [
        ("emily.carter@clinic.local", "Marylebone Clinic", 1, time(9, 0), time(17, 0)),
        ("emily.carter@clinic.local", "Marylebone Clinic", 3, time(9, 0), time(17, 0)),
        ("james.patel@clinic.local", "Canary Wharf Clinic", 2, time(10, 0), time(18, 0)),
        ("james.patel@clinic.local", "Canary Wharf Clinic", 4, time(10, 0), time(18, 0)),
    ]:
        schedule = (
            session.query(StaffSchedule)
            .filter_by(
                staff_id=staff_members[staff_email].id,
                branch_id=branches[branch_name].id,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
            )
            .one_or_none()
        )
        if schedule is None:
            schedule = StaffSchedule(
                staff=staff_members[staff_email],
                branch=branches[branch_name],
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
            )
            session.add(schedule)
        schedule.is_active = True

    exception_date = date.today() + timedelta(days=7)
    exception = (
        session.query(StaffScheduleException)
        .filter_by(
            staff_id=staff_members["emily.carter@clinic.local"].id,
            exception_date=exception_date,
            exception_type="day_off",
        )
        .one_or_none()
    )
    if exception is None:
        exception = StaffScheduleException(
            staff=staff_members["emily.carter@clinic.local"],
            branch=branches["Marylebone Clinic"],
            exception_date=exception_date,
            exception_type="day_off",
        )
        session.add(exception)
    exception.note = "Conference attendance"

    session.flush()
    return {"branches": branches, "staff_members": staff_members}


def upsert_services(session, service_categories: dict[str, ServiceCategory]) -> dict[str, Service]:
    services = {}
    for name, category_name, description, duration_min, base_price in [
        (
            "Initial Consultation",
            "General Dentistry",
            "Diagnostic consultation and treatment plan",
            45,
            Decimal("150.00"),
        ),
        (
            "Dental Cleaning",
            "General Dentistry",
            "Routine prophylaxis appointment",
            60,
            Decimal("220.00"),
        ),
        (
            "Orthodontic Evaluation",
            "Orthodontics",
            "Assessment for braces or aligners",
            50,
            Decimal("280.00"),
        ),
        (
            "Tooth Whitening",
            "Aesthetic Dentistry",
            "In-office whitening session",
            90,
            Decimal("600.00"),
        ),
    ]:
        service = get_by(session, Service, name=name)
        if service is None:
            service = Service(name=name)
            session.add(service)
        service.category = service_categories[category_name]
        service.description = description
        service.duration_min = duration_min
        service.base_price = base_price
        service.is_active = True
        services[name] = service

    session.flush()
    return services


def upsert_contacts_activity(
    session,
    channels: dict[str, Channel],
    appointment_statuses: dict[str, AppointmentStatus],
    conversation_statuses: dict[str, ConversationStatus],
    branches: dict[str, Branch],
    staff_members: dict[str, Staff],
    services: dict[str, Service],
) -> None:
    contacts = {}
    for email, full_name, phone, birth_date, notes, source_code, lifecycle_stage in [
        (
            "charlotte.hughes@example.com",
            "Charlotte Hughes",
            "+44 7700 900401",
            date(1991, 5, 17),
            "Interested in whitening and routine cleaning",
            "instagram",
            "qualified",
        ),
        (
            "oliver.reed@example.com",
            "Oliver Reed",
            "+44 7700 900402",
            date(1987, 9, 2),
            "Seeking orthodontic evaluation",
            "website",
            "booked",
        ),
    ]:
        contact = get_by(session, Contact, email=email)
        if contact is None:
            contact = Contact(email=email)
            session.add(contact)
        contact.full_name = full_name
        contact.phone = phone
        contact.birth_date = birth_date
        contact.notes = notes
        contact.source_channel = channels[source_code]
        contact.lifecycle_stage = lifecycle_stage
        contacts[email] = contact

    session.flush()

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    appointments = {}
    for key, contact_email, staff_email, branch_name, start_at, end_at, status_code, channel_code, comment in [
        (
            "charlotte_whitening",
            "charlotte.hughes@example.com",
            "emily.carter@clinic.local",
            "Marylebone Clinic",
            now + timedelta(days=2, hours=3),
            now + timedelta(days=2, hours=3, minutes=45),
            "confirmed",
            "instagram",
            "Booked after DM conversation",
        ),
        (
            "oliver_ortho",
            "oliver.reed@example.com",
            "james.patel@clinic.local",
            "Canary Wharf Clinic",
            now + timedelta(days=3, hours=5),
            now + timedelta(days=3, hours=5, minutes=50),
            "scheduled",
            "website",
            "Website lead follow-up",
        ),
    ]:
        appointment = (
            session.query(Appointment)
            .filter_by(contact_id=contacts[contact_email].id, start_at=start_at)
            .one_or_none()
        )
        if appointment is None:
            appointment = Appointment(
                contact=contacts[contact_email],
                start_at=start_at,
            )
            session.add(appointment)
        appointment.provider_staff = staff_members[staff_email]
        appointment.branch = branches[branch_name]
        appointment.end_at = end_at
        appointment.status = appointment_statuses[status_code]
        appointment.channel = channels[channel_code]
        appointment.comment = comment
        appointments[key] = appointment

    session.flush()

    for appointment_key, service_name, quantity in [
        ("charlotte_whitening", "Tooth Whitening", 1),
        ("oliver_ortho", "Orthodontic Evaluation", 1),
    ]:
        appointment_service = (
            session.query(AppointmentService)
            .filter_by(
                appointment_id=appointments[appointment_key].id,
                service_id=services[service_name].id,
            )
            .one_or_none()
        )
        if appointment_service is None:
            appointment_service = AppointmentService(
                appointment=appointments[appointment_key],
                service=services[service_name],
            )
            session.add(appointment_service)
        appointment_service.quantity = quantity
        appointment_service.price = services[service_name].base_price

    conversations = {}
    for chat_id, contact_email, channel_code, status_code, operator_email, handoff_status in [
        (
            "wa-charlotte-001",
            "charlotte.hughes@example.com",
            "whatsapp",
            "open",
            "olivia.bennett@clinic.local",
            "resolved",
        ),
        (
            "web-oliver-001",
            "oliver.reed@example.com",
            "website",
            "waiting_human",
            "olivia.bennett@clinic.local",
            "assigned",
        ),
    ]:
        conversation = get_by(session, Conversation, external_chat_id=chat_id)
        if conversation is None:
            conversation = Conversation(external_chat_id=chat_id)
            session.add(conversation)
        conversation.contact = contacts[contact_email]
        conversation.channel = channels[channel_code]
        conversation.status = conversation_statuses[status_code]
        conversation.operator = staff_members[operator_email]
        conversation.handoff_status = handoff_status
        conversations[chat_id] = conversation

    session.flush()

    for chat_id, direction, sender_type, message_text, external_message_id, sent_at in [
        (
            "wa-charlotte-001",
            "inbound",
            "contact",
            "Hi, I'd like to know more about whitening options.",
            "msg-wa-001",
            now - timedelta(hours=5),
        ),
        (
            "wa-charlotte-001",
            "outbound",
            "staff",
            "We have an opening this week at Marylebone. Would Thursday work for you?",
            "msg-wa-002",
            now - timedelta(hours=4, minutes=50),
        ),
        (
            "web-oliver-001",
            "inbound",
            "contact",
            "I want to schedule an orthodontic evaluation.",
            "msg-web-001",
            now - timedelta(hours=3),
        ),
    ]:
        message = get_by(session, Message, external_message_id=external_message_id)
        if message is None:
            message = Message(external_message_id=external_message_id)
            session.add(message)
        message.conversation = conversations[chat_id]
        message.direction = direction
        message.sender_type = sender_type
        message.message_text = message_text
        message.message_type = "text"
        message.sent_at = sent_at


def main() -> None:
    session = SessionLocal()
    try:
        reference_rows = upsert_reference_rows(session)
        clinic_rows = upsert_branches_and_staff(session)
        services = upsert_services(session, reference_rows["service_categories"])
        upsert_contacts_activity(
            session,
            channels=reference_rows["channels"],
            appointment_statuses=reference_rows["appointment_statuses"],
            conversation_statuses=reference_rows["conversation_statuses"],
            branches=clinic_rows["branches"],
            staff_members=clinic_rows["staff_members"],
            services=services,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Database seed completed.")


if __name__ == "__main__":
    main()
