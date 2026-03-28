"""
Appointment request domain — create and update draft booking records.

The appointment_request table is the staging area between a chatbot conversation
and a confirmed appointment. The bot fills it in incrementally as the patient
provides data across multiple messages.

Public API:
  upsert_appointment_request()  — create or update the open request for a conversation
  compute_missing_booking_fields()  — return which fields are still needed (testable pure fn)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppointmentRequest, Contact, Service, Staff
from app.modules.inbound_messages.constants import AppointmentRequestStatus

logger = logging.getLogger(__name__)

# Fields we consider required before the booking is complete enough to hand off.
BOOKING_REQUIRED_FIELDS: list[str] = ["service", "date_preference", "phone"]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def upsert_appointment_request(
    session: Session,
    contact_id: int,
    conversation_id: int,
    channel_id: int | None,
    source_message_id: int,
    extracted_entities: dict[str, Any],
) -> tuple[AppointmentRequest, list[str]]:
    """
    Create or update the open appointment_request for this conversation.

    - Looks for an existing 'new' or 'collecting_data' request for the conversation.
    - If found, merges any newly extracted entities into it.
    - If not found, creates a fresh record.
    - Updates the contact's name and phone if the entities contain new info.
    - Returns (appointment_request, missing_fields).

    missing_fields is the list of required booking fields that are still unknown.
    An empty list means all required data has been collected.
    """
    req = _find_open_request(session, conversation_id)
    now = datetime.now(UTC)

    if req is None:
        req = AppointmentRequest(
            contact_id=contact_id,
            conversation_id=conversation_id,
            channel_id=channel_id,
            source_message_id=source_message_id,
            status=AppointmentRequestStatus.NEW,
            urgency="normal",
            created_at=now,
            updated_at=now,
        )
        session.add(req)
        logger.info(
            "Created new appointment_request for contact=%s conversation=%s",
            contact_id,
            conversation_id,
        )

    changed = _merge_entities(session, req, extracted_entities)

    # Transition from NEW → COLLECTING_DATA as soon as we touch it.
    if req.status == AppointmentRequestStatus.NEW:
        req.status = AppointmentRequestStatus.COLLECTING_DATA
        changed = True

    if changed:
        req.updated_at = now

    # Update contact name/phone if the message contained new info.
    _update_contact_from_entities(session, contact_id, extracted_entities)

    session.flush()

    missing = compute_missing_booking_fields(session, req, contact_id)

    if not missing and req.status == AppointmentRequestStatus.COLLECTING_DATA:
        req.status = AppointmentRequestStatus.PENDING_ADMIN
        req.updated_at = datetime.now(UTC)
        session.flush()
        logger.info(
            "appointment_request id=%s is complete — moving to pending_admin",
            req.id,
        )

    return req, missing


def compute_missing_booking_fields(
    session: Session,
    req: AppointmentRequest,
    contact_id: int,
) -> list[str]:
    """
    Return the list of required booking fields that are still missing.

    A field is considered "collected" if either the structured DB column is
    populated OR the notes field records a free-text hint for it.
    """
    missing: list[str] = []

    # Service — either FK resolved or a free-text hint stored in notes.
    has_service = (
        req.requested_service_id is not None
        or (req.notes is not None and "service:" in req.notes.lower())
    )
    if not has_service:
        missing.append("service")

    # Date / time preference — either a parsed date or free-text time_range_notes.
    has_date = req.preferred_date is not None or bool(req.time_range_notes)
    if not has_date:
        missing.append("date_preference")

    # Phone number — must be on the contact record.
    contact = session.get(Contact, contact_id)
    if contact is not None and not contact.phone:
        missing.append("phone")

    return missing


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_open_request(
    session: Session,
    conversation_id: int,
) -> AppointmentRequest | None:
    """Return the most recent open appointment_request for this conversation."""
    return session.scalar(
        select(AppointmentRequest)
        .where(
            AppointmentRequest.conversation_id == conversation_id,
            AppointmentRequest.status.in_([
                AppointmentRequestStatus.NEW,
                AppointmentRequestStatus.COLLECTING_DATA,
            ]),
        )
        .order_by(AppointmentRequest.created_at.desc())
        .limit(1)
    )


def _merge_entities(
    session: Session,
    req: AppointmentRequest,
    entities: dict[str, Any],
) -> bool:
    """
    Merge extracted entities into the appointment_request.

    Returns True if any field was changed.
    """
    changed = False

    # Service: try to resolve to a DB row; fall back to a text note.
    if "service" in entities and req.requested_service_id is None:
        service_name: str = entities["service"]
        service = _find_service(session, service_name)
        if service:
            req.requested_service_id = service.id
            logger.debug("Matched service '%s' → id=%s", service_name, service.id)
        else:
            hint = f"service: {service_name}"
            req.notes = f"{req.notes}\n{hint}".strip() if req.notes else hint
            logger.debug("Service '%s' not found in DB — stored as note", service_name)
        changed = True

    # Date + time preference — stored as time_range_notes (raw text) until an
    # admin confirms an actual slot and creates the appointment.
    date_pref = entities.get("date_preference")
    time_pref = entities.get("time_preference")

    if (date_pref or time_pref) and not req.time_range_notes and req.preferred_date is None:
        parts = [p for p in [date_pref, time_pref] if p]
        req.time_range_notes = " ".join(parts)
        changed = True

    # Doctor preference: try to resolve to a DB staff row.
    if "doctor_preference" in entities and req.requested_provider_staff_id is None:
        doc_name: str = entities["doctor_preference"]
        staff = _find_staff(session, doc_name)
        if staff:
            req.requested_provider_staff_id = staff.id
            logger.debug(
                "Matched doctor '%s' → staff.id=%s", doc_name, staff.id
            )
            changed = True

    return changed


def _update_contact_from_entities(
    session: Session,
    contact_id: int,
    entities: dict[str, Any],
) -> None:
    """
    Patch the contact's name and phone if the message provided them and
    the contact doesn't already have these fields filled in.
    """
    contact = session.get(Contact, contact_id)
    if contact is None:
        return

    if "name" in entities and not contact.full_name:
        contact.full_name = entities["name"]
        logger.debug("Updated contact id=%s full_name from entities", contact_id)

    if "phone" in entities and not contact.phone:
        contact.phone = entities["phone"]
        logger.debug("Updated contact id=%s phone from entities", contact_id)


def _find_service(session: Session, name: str) -> Service | None:
    """Find an active service by case-insensitive partial match on name."""
    return session.scalar(
        select(Service)
        .where(
            Service.is_active.is_(True),
            Service.name.ilike(f"%{name}%"),
        )
        .limit(1)
    )


def _find_staff(session: Session, name: str) -> Staff | None:
    """Find an active appointable staff member by case-insensitive partial match."""
    return session.scalar(
        select(Staff)
        .where(
            Staff.is_active.is_(True),
            Staff.can_take_appointments.is_(True),
            Staff.full_name.ilike(f"%{name}%"),
        )
        .limit(1)
    )
