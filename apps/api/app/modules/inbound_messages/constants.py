"""
Shared string constants for intent classification, routing, and conversation management.

All magic strings used in the inbound message pipeline are defined here.
DB check constraints, Gemini prompts, and service logic all reference these values.
"""


class IntentCode:
    """Intent codes matching the 28-intent taxonomy in intentions.md."""

    # New client intents
    GREETING = "greeting"
    PRICE_QUESTION = "price_question"
    SERVICE_INFO = "service_info"
    APPOINTMENT_REQUEST = "appointment_request"
    APPOINTMENT_AVAILABILITY = "appointment_availability"
    EMERGENCY = "emergency"
    CLINIC_HOURS = "clinic_hours"
    LOCATION_QUESTION = "location_question"
    DOCTOR_QUESTION = "doctor_question"
    INSURANCE_OR_DOCUMENTS = "insurance_or_documents"
    FIRST_VISIT_QUESTION = "first_visit_question"
    PROMOTION_INTEREST = "promotion_interest"

    # Existing patient intents
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    CONFIRM_APPOINTMENT = "confirm_appointment"
    APPOINTMENT_DETAILS = "appointment_details"
    POST_VISIT_FOLLOWUP = "post_visit_followup"
    TREATMENT_PLAN_QUESTION = "treatment_plan_question"
    REPEAT_SERVICE_REQUEST = "repeat_service_request"
    RESULTS_OR_RECORDS_REQUEST = "results_or_records_request"

    # Universal intents
    CONTACT_REQUEST = "contact_request"
    LEAVE_CONTACT = "leave_contact"
    PROVIDE_BOOKING_DATA = "provide_booking_data"
    FAQ_GENERAL = "faq_general"
    COMPLAINT_OR_NEGATIVE_FEEDBACK = "complaint_or_negative_feedback"
    GRATITUDE_OR_POSITIVE_FEEDBACK = "gratitude_or_positive_feedback"
    NON_RELEVANT_MESSAGE = "non_relevant_message"
    UNKNOWN = "unknown"

    ALL = frozenset({
        GREETING, PRICE_QUESTION, SERVICE_INFO, APPOINTMENT_REQUEST,
        APPOINTMENT_AVAILABILITY, EMERGENCY, CLINIC_HOURS, LOCATION_QUESTION,
        DOCTOR_QUESTION, INSURANCE_OR_DOCUMENTS, FIRST_VISIT_QUESTION,
        PROMOTION_INTEREST, RESCHEDULE_APPOINTMENT, CANCEL_APPOINTMENT,
        CONFIRM_APPOINTMENT, APPOINTMENT_DETAILS, POST_VISIT_FOLLOWUP,
        TREATMENT_PLAN_QUESTION, REPEAT_SERVICE_REQUEST,
        RESULTS_OR_RECORDS_REQUEST, CONTACT_REQUEST, LEAVE_CONTACT,
        PROVIDE_BOOKING_DATA, FAQ_GENERAL, COMPLAINT_OR_NEGATIVE_FEEDBACK,
        GRATITUDE_OR_POSITIVE_FEEDBACK, NON_RELEVANT_MESSAGE, UNKNOWN,
    })

    MVP = frozenset({
        GREETING, PRICE_QUESTION, SERVICE_INFO, APPOINTMENT_REQUEST,
        APPOINTMENT_AVAILABILITY, EMERGENCY, CLINIC_HOURS, LOCATION_QUESTION,
        RESCHEDULE_APPOINTMENT, CANCEL_APPOINTMENT, CONFIRM_APPOINTMENT,
        POST_VISIT_FOLLOWUP, INSURANCE_OR_DOCUMENTS, CONTACT_REQUEST, UNKNOWN,
    })


class RouteType:
    """How the bot should handle a classified intent."""

    AUTO_REPLY = "auto_reply"
    AUTO_REPLY_AND_COLLECT = "auto_reply_and_collect"
    HANDOFF_ADMIN = "handoff_admin"
    HANDOFF_URGENT = "handoff_urgent"
    SILENT_IGNORE = "silent_ignore"

    ALL = frozenset({
        AUTO_REPLY, AUTO_REPLY_AND_COLLECT,
        HANDOFF_ADMIN, HANDOFF_URGENT, SILENT_IGNORE,
    })


# Maps each intent to its default route type (from intentions_flow.md).
INTENT_ROUTE_MAP: dict[str, str] = {
    IntentCode.GREETING:                       RouteType.AUTO_REPLY,
    IntentCode.PRICE_QUESTION:                 RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.SERVICE_INFO:                   RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.APPOINTMENT_REQUEST:            RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.APPOINTMENT_AVAILABILITY:       RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.EMERGENCY:                      RouteType.HANDOFF_URGENT,
    IntentCode.CLINIC_HOURS:                   RouteType.AUTO_REPLY,
    IntentCode.LOCATION_QUESTION:              RouteType.AUTO_REPLY,
    IntentCode.DOCTOR_QUESTION:                RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.INSURANCE_OR_DOCUMENTS:         RouteType.HANDOFF_ADMIN,
    IntentCode.FIRST_VISIT_QUESTION:           RouteType.AUTO_REPLY,
    IntentCode.PROMOTION_INTEREST:             RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.RESCHEDULE_APPOINTMENT:         RouteType.HANDOFF_ADMIN,
    IntentCode.CANCEL_APPOINTMENT:             RouteType.HANDOFF_ADMIN,
    IntentCode.CONFIRM_APPOINTMENT:            RouteType.AUTO_REPLY,
    IntentCode.APPOINTMENT_DETAILS:            RouteType.HANDOFF_ADMIN,
    IntentCode.POST_VISIT_FOLLOWUP:            RouteType.HANDOFF_ADMIN,
    IntentCode.TREATMENT_PLAN_QUESTION:        RouteType.HANDOFF_ADMIN,
    IntentCode.REPEAT_SERVICE_REQUEST:         RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.RESULTS_OR_RECORDS_REQUEST:     RouteType.HANDOFF_ADMIN,
    IntentCode.CONTACT_REQUEST:                RouteType.HANDOFF_ADMIN,
    IntentCode.LEAVE_CONTACT:                  RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.PROVIDE_BOOKING_DATA:           RouteType.AUTO_REPLY_AND_COLLECT,
    IntentCode.FAQ_GENERAL:                    RouteType.AUTO_REPLY,
    IntentCode.COMPLAINT_OR_NEGATIVE_FEEDBACK: RouteType.HANDOFF_ADMIN,
    IntentCode.GRATITUDE_OR_POSITIVE_FEEDBACK: RouteType.AUTO_REPLY,
    IntentCode.NON_RELEVANT_MESSAGE:           RouteType.AUTO_REPLY,
    IntentCode.UNKNOWN:                        RouteType.AUTO_REPLY_AND_COLLECT,
}


class ConversationStatusCode:
    """Status codes matching the seed data in seed_db.py."""

    NEW_INCOMING = "new_incoming"
    CLASSIFIED = "classified"
    WAITING_FOR_PATIENT_DATA = "waiting_for_patient_data"
    WAITING_FOR_PATIENT_REPLY = "waiting_for_patient_reply"
    WAITING_FOR_ADMIN = "waiting_for_admin"
    URGENT_HANDOFF = "urgent_handoff"
    BOOKING_REQUEST_CREATED = "booking_request_created"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_CANCEL_REQUESTED = "appointment_cancel_requested"
    APPOINTMENT_RESCHEDULE_REQUESTED = "appointment_reschedule_requested"
    RESOLVED = "resolved"
    SPAM = "spam"


# Intents that should trigger appointment_request create/update logic.
BOOKING_INTENTS = frozenset({
    IntentCode.APPOINTMENT_REQUEST,
    IntentCode.PROVIDE_BOOKING_DATA,
    IntentCode.APPOINTMENT_AVAILABILITY,
    IntentCode.REPEAT_SERVICE_REQUEST,
})


class AppointmentRequestStatus:
    """Statuses for the appointment_request lifecycle."""

    NEW = "new"
    COLLECTING_DATA = "collecting_data"
    PENDING_ADMIN = "pending_admin"
    SLOT_OFFERED = "slot_offered"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class HandoffTaskType:
    """Task types for handoff_tasks."""

    ADMIN_FOLLOWUP = "admin_followup"
    URGENT_CASE = "urgent_case"
    DOCUMENT_REQUEST = "document_request"
    CALLBACK_REQUEST = "callback_request"
    COMPLAINT = "complaint"
    POST_VISIT = "post_visit"
    MANUAL_BOOKING = "manual_booking"
    MANUAL_RESCHEDULE = "manual_reschedule"
    MANUAL_CANCEL = "manual_cancel"


class Priority:
    """Priority levels shared by conversations and handoff_tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
