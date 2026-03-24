from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from app.db.models import (
    Appointment,
    AppointmentRequest,
    AppointmentService,
    AppointmentStatus,
    Branch,
    BranchHour,
    Channel,
    Contact,
    ContactChannelIdentity,
    Conversation,
    ConversationIntent,
    ConversationStatus,
    HandoffTask,
    Message,
    Service,
    ServiceCategory,
    Staff,
    StaffBranch,
    StaffSchedule,
    StaffScheduleException,
    StaffService,
)
from app.db.session import SessionLocal


def get_by(session, model, **filters):
    return session.query(model).filter_by(**filters).one_or_none()


def upsert_reference_rows(session) -> dict[str, dict[str, object]]:
    channels = {}
    for code, display_name, notes in [
        ("instagram", "Instagram Direct", "Inbound social channel"),
        ("telegram", "Telegram", "Messaging channel for patient support"),
        ("whatsapp", "WhatsApp", "Primary chat channel"),
        ("website", "Website", "Lead capture forms"),
        ("website_live_chat", "Website live chat", "Live chat widget on the clinic site"),
        ("phone", "Phone", "Direct call bookings"),
        ("email", "Email", "Document and customer support requests"),
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
        ("new_incoming", "New incoming", "A new inbound message arrived"),
        ("classified", "Classified", "Intent has been classified"),
        ("waiting_for_patient_data", "Waiting for patient data", "Bot is collecting missing booking data"),
        ("waiting_for_patient_reply", "Waiting for patient reply", "Bot is waiting for the patient to answer"),
        ("waiting_for_admin", "Waiting for admin", "Human follow-up is required"),
        ("urgent_handoff", "Urgent handoff", "Conversation needs immediate review"),
        ("booking_request_created", "Booking request created", "Draft booking request was created"),
        ("appointment_confirmed", "Appointment confirmed", "Patient confirmed the booked visit"),
        ("appointment_cancel_requested", "Appointment cancel requested", "Patient asked to cancel a visit"),
        ("appointment_reschedule_requested", "Appointment reschedule requested", "Patient asked to reschedule a visit"),
        ("resolved", "Resolved", "Conversation has been completed"),
        ("spam", "Spam", "Spam or irrelevant message"),
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
    for name, address, phone, parking_info, directions, map_url in [
        (
            "Marylebone Clinic",
            "221B Baker Street, Marylebone, London",
            "+44 20 7946 0100",
            "Paid parking available in the next block after 18:00.",
            "Exit Baker Street station, walk 4 minutes toward Baker Street.",
            "https://maps.example.com/marylebone-clinic",
        ),
        (
            "Canary Wharf Clinic",
            "14 Bank Street, Canary Wharf, London",
            "+44 20 7946 0200",
            "Underground parking in the building with patient discount validation.",
            "Use Canary Wharf station exit B and follow the Bank Street signs.",
            "https://maps.example.com/canary-wharf-clinic",
        ),
    ]:
        branch = get_by(session, Branch, name=name)
        if branch is None:
            branch = Branch(name=name)
            session.add(branch)
        branch.address = address
        branch.phone = phone
        branch.parking_info = parking_info
        branch.directions = directions
        branch.map_url = map_url
        branch.timezone = "Europe/London"
        branch.is_active = True
        branches[name] = branch

    session.flush()

    for branch_name, weekday, open_time, close_time, notes in [
        ("Marylebone Clinic", 0, time(9, 0), time(18, 0), "Standard weekday hours"),
        ("Marylebone Clinic", 1, time(9, 0), time(18, 0), "Standard weekday hours"),
        ("Marylebone Clinic", 2, time(9, 0), time(18, 0), "Standard weekday hours"),
        ("Marylebone Clinic", 3, time(9, 0), time(18, 0), "Standard weekday hours"),
        ("Marylebone Clinic", 4, time(9, 0), time(18, 0), "Standard weekday hours"),
        ("Marylebone Clinic", 5, time(10, 0), time(16, 0), "Saturday by appointment"),
        ("Canary Wharf Clinic", 0, time(8, 30), time(19, 0), "Extended weekday hours"),
        ("Canary Wharf Clinic", 1, time(8, 30), time(19, 0), "Extended weekday hours"),
        ("Canary Wharf Clinic", 2, time(8, 30), time(19, 0), "Extended weekday hours"),
        ("Canary Wharf Clinic", 3, time(8, 30), time(19, 0), "Extended weekday hours"),
        ("Canary Wharf Clinic", 4, time(8, 30), time(19, 0), "Extended weekday hours"),
        ("Canary Wharf Clinic", 5, time(9, 0), time(14, 0), "Saturday by appointment"),
    ]:
        branch_hour = (
            session.query(BranchHour)
            .filter_by(
                branch_id=branches[branch_name].id,
                weekday=weekday,
                open_time=open_time,
                close_time=close_time,
            )
            .one_or_none()
        )
        if branch_hour is None:
            branch_hour = BranchHour(
                branch=branches[branch_name],
                weekday=weekday,
                open_time=open_time,
                close_time=close_time,
            )
            session.add(branch_hour)
        branch_hour.is_active = True
        branch_hour.notes = notes

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
            "Sophia Turner",
            "admin",
            None,
            "+44 7700 900150",
            "sophia.turner@clinic.local",
            True,
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
        ("sophia.turner@clinic.local", "Marylebone Clinic", True),
        ("sophia.turner@clinic.local", "Canary Wharf Clinic", False),
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
        ("james.patel@clinic.local", "Canary Wharf Clinic", 0, time(10, 0), time(18, 0)),
        ("james.patel@clinic.local", "Canary Wharf Clinic", 2, time(10, 0), time(18, 0)),
        ("james.patel@clinic.local", "Canary Wharf Clinic", 4, time(10, 0), time(18, 0)),
        ("sophia.turner@clinic.local", "Marylebone Clinic", 0, time(8, 30), time(17, 30)),
        ("sophia.turner@clinic.local", "Marylebone Clinic", 1, time(8, 30), time(17, 30)),
        ("olivia.bennett@clinic.local", "Marylebone Clinic", 0, time(9, 0), time(18, 0)),
        ("olivia.bennett@clinic.local", "Marylebone Clinic", 1, time(9, 0), time(18, 0)),
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


def upsert_staff_services(
    session,
    branches: dict[str, Branch],
    staff_members: dict[str, Staff],
    services: dict[str, Service],
) -> None:
    for staff_email, service_name, branch_name, notes in [
        (
            "emily.carter@clinic.local",
            "Orthodontic Evaluation",
            "Marylebone Clinic",
            "Primary orthodontic consultations",
        ),
        (
            "emily.carter@clinic.local",
            "Tooth Whitening",
            "Marylebone Clinic",
            "Cosmetic treatments by senior clinician",
        ),
        (
            "james.patel@clinic.local",
            "Initial Consultation",
            "Canary Wharf Clinic",
            "General intake and diagnosis",
        ),
        (
            "james.patel@clinic.local",
            "Dental Cleaning",
            "Canary Wharf Clinic",
            "Routine hygiene and maintenance",
        ),
    ]:
        capability = (
            session.query(StaffService)
            .filter_by(
                staff_id=staff_members[staff_email].id,
                service_id=services[service_name].id,
                branch_id=branches[branch_name].id,
            )
            .one_or_none()
        )
        if capability is None:
            capability = StaffService(
                staff=staff_members[staff_email],
                service=services[service_name],
                branch=branches[branch_name],
            )
            session.add(capability)
        capability.is_active = True
        capability.notes = notes

    session.flush()


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
            "Warm lead interested in Saturday cleaning appointment.",
            "instagram",
            "qualified",
        ),
        (
            "oliver.reed@example.com",
            "Oliver Reed",
            "+44 7700 900402",
            date(1987, 9, 2),
            "Upcoming orthodontic evaluation confirmed.",
            "website",
            "booked",
        ),
        (
            "amelia.stone@example.com",
            "Amelia Stone",
            "+44 7700 900403",
            date(1990, 1, 28),
            "Post-treatment follow-up requires clinician review.",
            "whatsapp",
            "patient",
        ),
        (
            "noah.campbell@example.com",
            "Noah Campbell",
            "+44 7700 900404",
            date(1984, 11, 3),
            "Requested invoice copy via email.",
            "email",
            "patient",
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

    for contact_email, channel_code, external_id, username in [
        (
            "charlotte.hughes@example.com",
            "instagram",
            "ig-charlotte-hughes",
            "charlotte_h",
        ),
        (
            "oliver.reed@example.com",
            "website",
            "web-visitor-oliver-001",
            None,
        ),
        (
            "amelia.stone@example.com",
            "whatsapp",
            "wa-447700900403",
            None,
        ),
        (
            "noah.campbell@example.com",
            "email",
            "noah.campbell@example.com",
            None,
        ),
    ]:
        identity = (
            session.query(ContactChannelIdentity)
            .filter_by(
                channel_id=channels[channel_code].id,
                external_id=external_id,
            )
            .one_or_none()
        )
        if identity is None:
            identity = ContactChannelIdentity(
                channel=channels[channel_code],
                external_id=external_id,
            )
            session.add(identity)
        identity.contact = contacts[contact_email]
        identity.username = username
        identity.phone = contacts[contact_email].phone
        identity.email = contacts[contact_email].email

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    appointments = {}
    for key, contact_email, staff_email, branch_name, start_at, end_at, status_code, channel_code, comment in [
        (
            "oliver_ortho",
            "oliver.reed@example.com",
            "emily.carter@clinic.local",
            "Marylebone Clinic",
            now + timedelta(days=3, hours=4),
            now + timedelta(days=3, hours=4, minutes=50),
            "confirmed",
            "website",
            "Confirmed after web booking flow",
        ),
        (
            "amelia_cleaning_completed",
            "amelia.stone@example.com",
            "james.patel@clinic.local",
            "Canary Wharf Clinic",
            now - timedelta(days=2, hours=2),
            now - timedelta(days=2, hours=1),
            "completed",
            "whatsapp",
            "Completed hygiene visit before follow-up chat",
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
        ("oliver_ortho", "Orthodontic Evaluation", 1),
        ("amelia_cleaning_completed", "Dental Cleaning", 1),
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
    for chat_id, contact_email, channel_code, status_code, operator_email, handoff_status, priority, is_spam in [
        (
            "wa-charlotte-001",
            "charlotte.hughes@example.com",
            "whatsapp",
            "booking_request_created",
            "sophia.turner@clinic.local",
            "assigned",
            "normal",
            False,
        ),
        (
            "web-oliver-001",
            "oliver.reed@example.com",
            "website",
            "appointment_confirmed",
            "sophia.turner@clinic.local",
            "resolved",
            "normal",
            False,
        ),
        (
            "wa-amelia-001",
            "amelia.stone@example.com",
            "whatsapp",
            "urgent_handoff",
            "sophia.turner@clinic.local",
            "requested",
            "urgent",
            False,
        ),
        (
            "email-noah-001",
            "noah.campbell@example.com",
            "email",
            "waiting_for_admin",
            "sophia.turner@clinic.local",
            "assigned",
            "normal",
            False,
        ),
        (
            "wa-spam-001",
            None,
            "whatsapp",
            "spam",
            None,
            "none",
            "low",
            True,
        ),
    ]:
        conversation = get_by(session, Conversation, external_chat_id=chat_id)
        if conversation is None:
            conversation = Conversation(external_chat_id=chat_id)
            session.add(conversation)
        conversation.contact = contacts.get(contact_email) if contact_email else None
        conversation.channel = channels[channel_code]
        conversation.status = conversation_statuses[status_code]
        conversation.operator = (
            staff_members[operator_email] if operator_email is not None else None
        )
        conversation.handoff_status = handoff_status
        conversation.priority = priority
        conversation.is_spam = is_spam
        conversations[chat_id] = conversation

    session.flush()

    messages = {}
    for chat_id, direction, sender_type, message_text, external_message_id, sent_at in [
        (
            "wa-charlotte-001",
            "inbound",
            "contact",
            "Hi, I want dental cleaning this Saturday after 2pm. My name is Charlotte.",
            "msg-wa-001",
            now - timedelta(hours=6),
        ),
        (
            "wa-charlotte-001",
            "outbound",
            "bot",
            "Thanks, Charlotte. I have created your booking request and our administrator will confirm the slot.",
            "msg-wa-002",
            now - timedelta(hours=5, minutes=55),
        ),
        (
            "web-oliver-001",
            "inbound",
            "contact",
            "Yes, I confirm the orthodontic appointment.",
            "msg-web-001",
            now - timedelta(hours=4),
        ),
        (
            "wa-amelia-001",
            "inbound",
            "contact",
            "After the extraction I have strong swelling and bleeding, please call me urgently.",
            "msg-wa-003",
            now - timedelta(hours=2),
        ),
        (
            "email-noah-001",
            "inbound",
            "contact",
            "Please send my invoice and treatment summary to my email.",
            "msg-email-001",
            now - timedelta(hours=1, minutes=30),
        ),
        (
            "wa-spam-001",
            "inbound",
            "integration",
            "Cheap followers for your clinic profile!",
            "msg-wa-spam-001",
            now - timedelta(minutes=40),
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
        messages[external_message_id] = message

    session.flush()

    appointment_request = (
        session.query(AppointmentRequest)
        .filter_by(conversation_id=conversations["wa-charlotte-001"].id)
        .one_or_none()
    )
    if appointment_request is None:
        appointment_request = AppointmentRequest(
            contact=contacts["charlotte.hughes@example.com"],
            conversation=conversations["wa-charlotte-001"],
        )
        session.add(appointment_request)
    appointment_request.branch = branches["Marylebone Clinic"]
    appointment_request.requested_service = services["Dental Cleaning"]
    appointment_request.requested_provider = None
    appointment_request.preferred_date = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 or 7)
    appointment_request.preferred_time = time(14, 0)
    appointment_request.time_range_notes = "after 14:00"
    appointment_request.channel = channels["whatsapp"]
    appointment_request.source_message = messages["msg-wa-001"]
    appointment_request.status = "pending_admin"
    appointment_request.urgency = "normal"
    appointment_request.notes = "Requested Saturday cleaning from WhatsApp chat."

    session.flush()

    for chat_id, message_id, intent_code, route_type, confidence, extracted_entities in [
        (
            "wa-charlotte-001",
            "msg-wa-001",
            "appointment_request",
            "auto_reply_and_collect",
            Decimal("0.980"),
            {
                "name": "Charlotte Hughes",
                "service": "Dental Cleaning",
                "date_preference": "Saturday",
                "time_preference": "after 14:00",
                "phone_present": True,
            },
        ),
        (
            "web-oliver-001",
            "msg-web-001",
            "confirm_appointment",
            "auto_reply",
            Decimal("0.995"),
            {"has_active_appointment": True},
        ),
        (
            "wa-amelia-001",
            "msg-wa-003",
            "post_visit_followup",
            "handoff_urgent",
            Decimal("0.970"),
            {"symptoms": ["swelling", "bleeding"], "needs_callback": True},
        ),
        (
            "email-noah-001",
            "msg-email-001",
            "insurance_or_documents",
            "handoff_admin",
            Decimal("0.960"),
            {"requested_materials": ["invoice", "treatment_summary"], "delivery_channel": "email"},
        ),
        (
            "wa-spam-001",
            "msg-wa-spam-001",
            "non_relevant_message",
            "silent_ignore",
            Decimal("0.999"),
            {"spam": True},
        ),
    ]:
        intent = (
            session.query(ConversationIntent)
            .filter_by(
                conversation_id=conversations[chat_id].id,
                message_id=messages[message_id].id,
                intent_code=intent_code,
            )
            .one_or_none()
        )
        if intent is None:
            intent = ConversationIntent(
                conversation=conversations[chat_id],
                message=messages[message_id],
                intent_code=intent_code,
            )
            session.add(intent)
        intent.route_type = route_type
        intent.confidence = confidence
        intent.is_primary = True
        intent.extracted_entities = extracted_entities

    for conversation_key, task_type, priority, status, assigned_staff_email, payload, due_at, request in [
        (
            "wa-charlotte-001",
            "manual_booking",
            "normal",
            "assigned",
            "sophia.turner@clinic.local",
            {
                "service": "Dental Cleaning",
                "preferred_date": "Saturday",
                "preferred_time": "14:00",
                "next_step": "Confirm exact slot with patient",
            },
            now + timedelta(hours=4),
            appointment_request,
        ),
        (
            "wa-amelia-001",
            "urgent_case",
            "urgent",
            "new",
            "sophia.turner@clinic.local",
            {
                "reason": "Post-treatment symptoms with swelling and bleeding",
                "action": "Immediate callback and clinician review",
            },
            now + timedelta(minutes=15),
            None,
        ),
        (
            "email-noah-001",
            "document_request",
            "normal",
            "assigned",
            "sophia.turner@clinic.local",
            {
                "documents": ["invoice", "treatment_summary"],
                "delivery_channel": "email",
            },
            now + timedelta(hours=8),
            None,
        ),
    ]:
        task = (
            session.query(HandoffTask)
            .filter_by(
                conversation_id=conversations[conversation_key].id,
                task_type=task_type,
            )
            .one_or_none()
        )
        if task is None:
            task = HandoffTask(
                conversation=conversations[conversation_key],
                task_type=task_type,
            )
            session.add(task)
        task.contact = conversations[conversation_key].contact
        task.appointment_request = request
        task.assigned_staff = staff_members[assigned_staff_email]
        task.priority = priority
        task.status = status
        task.payload = payload
        task.due_at = due_at


def main() -> None:
    session = SessionLocal()
    try:
        reference_rows = upsert_reference_rows(session)
        clinic_rows = upsert_branches_and_staff(session)
        services = upsert_services(session, reference_rows["service_categories"])
        upsert_staff_services(
            session,
            branches=clinic_rows["branches"],
            staff_members=clinic_rows["staff_members"],
            services=services,
        )
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
