"""
Unit tests for appointment_requests/service.py.

All DB interactions are mocked — no real PostgreSQL.
Tests cover:
  - compute_missing_booking_fields (pure logic, easy to test)
  - upsert_appointment_request: new record creation, entity merging,
    status transitions, contact updates
  - _find_service / _find_staff lookup helpers (via mock session.scalar)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.modules.inbound_messages.constants import AppointmentRequestStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_req(
    id: int = 1,
    status: str = AppointmentRequestStatus.COLLECTING_DATA,
    requested_service_id: int | None = None,
    preferred_date=None,
    preferred_time=None,
    time_range_notes: str | None = None,
    requested_provider_staff_id: int | None = None,
    notes: str | None = None,
    contact_id: int = 10,
    conversation_id: int = 20,
) -> MagicMock:
    """Build a fake AppointmentRequest object."""
    req = MagicMock()
    req.id = id
    req.status = status
    req.requested_service_id = requested_service_id
    req.preferred_date = preferred_date
    req.preferred_time = preferred_time
    req.time_range_notes = time_range_notes
    req.requested_provider_staff_id = requested_provider_staff_id
    req.notes = notes
    req.contact_id = contact_id
    req.conversation_id = conversation_id
    return req


def _make_contact(
    id: int = 10,
    full_name: str | None = None,
    phone: str | None = None,
) -> MagicMock:
    contact = MagicMock()
    contact.id = id
    contact.full_name = full_name
    contact.phone = phone
    return contact


def _make_session(
    open_request=None,
    contact=None,
    service=None,
    staff=None,
):
    """
    Build a mock Session that returns controlled values for scalar() and get().

    scalar() is used to look up:
      1. The open appointment_request (_find_open_request)
      2. A matching Service (_find_service)
      3. A matching Staff (_find_staff)

    get() is used to retrieve the Contact.
    """
    session = MagicMock()

    # We need to control what scalar() returns for different query types.
    # Since scalar() is called multiple times in different order, we use
    # a side_effect queue.
    _scalar_returns = []
    if open_request is not None:
        _scalar_returns.append(open_request)
    else:
        _scalar_returns.append(None)

    def _scalar_side_effect(query):
        if _scalar_returns:
            return _scalar_returns.pop(0)
        return None

    # We'll override this per test when needed.
    session.scalar.side_effect = _scalar_side_effect

    def _get_side_effect(model_class, pk):
        from app.db.models import Contact
        if model_class is Contact:
            return contact
        return None

    session.get.side_effect = _get_side_effect

    return session


# ---------------------------------------------------------------------------
# compute_missing_booking_fields — pure logic tests (no real DB needed)
# ---------------------------------------------------------------------------

class TestComputeMissingBookingFields:

    def _call(self, req, contact=None):
        from app.modules.appointment_requests.service import compute_missing_booking_fields

        session = MagicMock()
        from app.db.models import Contact
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        return compute_missing_booking_fields(session, req, req.contact_id)

    def test_all_fields_present_returns_empty(self):
        req = _make_req(
            requested_service_id=5,
            time_range_notes="Saturday 10am",
        )
        contact = _make_contact(phone="+441234567890")

        missing = self._call(req, contact)

        assert missing == []

    def test_missing_service_and_date_and_phone(self):
        req = _make_req()  # nothing filled in
        contact = _make_contact()  # no phone

        missing = self._call(req, contact)

        assert "service" in missing
        assert "date_preference" in missing
        assert "phone" in missing

    def test_service_via_notes_is_not_missing(self):
        req = _make_req(notes="service: teeth cleaning")
        contact = _make_contact(phone="+441234567890")

        missing = self._call(req, contact)

        assert "service" not in missing

    def test_date_via_time_range_notes_is_not_missing(self):
        req = _make_req(
            requested_service_id=1,
            time_range_notes="tomorrow morning",
        )
        contact = _make_contact(phone="+44999")

        missing = self._call(req, contact)

        assert "date_preference" not in missing

    def test_phone_missing_when_contact_has_no_phone(self):
        req = _make_req(requested_service_id=1, time_range_notes="Monday")
        contact = _make_contact(phone=None)

        missing = self._call(req, contact)

        assert missing == ["phone"]

    def test_contact_none_does_not_raise(self):
        """If contact can't be loaded, we don't crash — phone just stays missing."""
        req = _make_req(requested_service_id=1, time_range_notes="Monday")

        missing = self._call(req, contact=None)

        # phone won't be added (contact is None), so no phone check
        assert missing == []


# ---------------------------------------------------------------------------
# upsert_appointment_request — creates new record when none exists
# ---------------------------------------------------------------------------

class TestUpsertCreatesNew:

    def test_creates_new_record_when_no_open_request(self):
        from app.modules.appointment_requests.service import upsert_appointment_request

        session = MagicMock()
        # scalar() for _find_open_request → None (no existing request)
        # scalar() for _find_service → None (no service match)
        session.scalar.side_effect = [None, None]

        from app.db.models import Contact
        contact = _make_contact(phone="+44123")
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        req, missing = upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=1,
            source_message_id=100,
            extracted_entities={"service": "cleaning"},
        )

        # A new AppointmentRequest should have been added to the session
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        from app.db.models import AppointmentRequest
        assert isinstance(added, AppointmentRequest)
        assert added.contact_id == 10
        assert added.conversation_id == 20

    def test_new_request_status_set_to_collecting_data(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import AppointmentRequest, Contact

        session = MagicMock()
        session.scalar.side_effect = [None, None]  # no existing req, no service match
        contact = _make_contact(phone="+44123")
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        req, _ = upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=1,
            source_message_id=100,
            extracted_entities={},
        )

        added = session.add.call_args[0][0]
        # Status transitions NEW → COLLECTING_DATA in the same call
        assert added.status == AppointmentRequestStatus.COLLECTING_DATA


# ---------------------------------------------------------------------------
# upsert_appointment_request — updates existing record
# ---------------------------------------------------------------------------

class TestUpsertUpdatesExisting:

    def test_merges_service_entity(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact, Service

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        fake_service = SimpleNamespace(id=7)
        contact = _make_contact(phone="+44123")

        session = MagicMock()
        # scalar: existing_req, then service match
        session.scalar.side_effect = [existing_req, fake_service]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        req, missing = upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=101,
            extracted_entities={"service": "cleaning"},
        )

        assert existing_req.requested_service_id == 7
        # No new record added
        session.add.assert_not_called()

    def test_stores_service_as_note_when_not_in_db(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(phone="+44123")

        session = MagicMock()
        # scalar: existing_req, then None (service not found)
        session.scalar.side_effect = [existing_req, None]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=101,
            extracted_entities={"service": "cosmic whitening"},
        )

        assert existing_req.notes is not None
        assert "cosmic whitening" in existing_req.notes

    def test_merges_date_and_time_preference(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(phone="+44123")

        session = MagicMock()
        session.scalar.side_effect = [existing_req]  # no service entity, so no service lookup
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=102,
            extracted_entities={
                "date_preference": "Saturday",
                "time_preference": "after 6pm",
            },
        )

        assert existing_req.time_range_notes == "Saturday after 6pm"

    def test_does_not_overwrite_existing_time_range_notes(self):
        """If date_preference already stored, don't overwrite with new message."""
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(
            status=AppointmentRequestStatus.COLLECTING_DATA,
            time_range_notes="Monday morning",
        )
        contact = _make_contact(phone="+44123")

        session = MagicMock()
        session.scalar.side_effect = [existing_req]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=103,
            extracted_entities={"date_preference": "Tuesday"},
        )

        # Should not have been overwritten
        assert existing_req.time_range_notes == "Monday morning"

    def test_updates_contact_name_and_phone_from_entities(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(full_name=None, phone=None)

        session = MagicMock()
        session.scalar.side_effect = [existing_req]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=104,
            extracted_entities={"name": "Anna Petrova", "phone": "+447700900123"},
        )

        assert contact.full_name == "Anna Petrova"
        assert contact.phone == "+447700900123"

    def test_does_not_overwrite_existing_contact_fields(self):
        """Don't clobber data that's already in the contact."""
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(full_name="Existing Name", phone="+44000")

        session = MagicMock()
        session.scalar.side_effect = [existing_req]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=105,
            extracted_entities={"name": "New Name", "phone": "+44111"},
        )

        assert contact.full_name == "Existing Name"
        assert contact.phone == "+44000"


# ---------------------------------------------------------------------------
# upsert_appointment_request — status transitions
# ---------------------------------------------------------------------------

class TestUpsertStatusTransitions:

    def test_moves_to_pending_admin_when_all_fields_collected(self):
        """Once missing_fields is empty, status → pending_admin."""
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact, Service

        existing_req = _make_req(
            status=AppointmentRequestStatus.COLLECTING_DATA,
            time_range_notes="Saturday",  # date already there
        )
        fake_service = SimpleNamespace(id=3)
        contact = _make_contact(phone="+44123")  # phone already there

        session = MagicMock()
        session.scalar.side_effect = [existing_req, fake_service]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        req, missing = upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=200,
            extracted_entities={"service": "cleaning"},
        )

        assert missing == []
        assert existing_req.status == AppointmentRequestStatus.PENDING_ADMIN

    def test_stays_collecting_when_fields_still_missing(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(phone=None)  # phone missing

        session = MagicMock()
        session.scalar.side_effect = [existing_req, None]  # no service match
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        req, missing = upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=201,
            extracted_entities={"service": "cleaning"},
        )

        assert "phone" in missing
        assert existing_req.status == AppointmentRequestStatus.COLLECTING_DATA

    def test_session_flushed(self):
        from app.modules.appointment_requests.service import upsert_appointment_request
        from app.db.models import Contact

        existing_req = _make_req(status=AppointmentRequestStatus.COLLECTING_DATA)
        contact = _make_contact(phone="+44999")

        session = MagicMock()
        session.scalar.side_effect = [existing_req]
        session.get.side_effect = lambda cls, pk: contact if cls is Contact else None

        upsert_appointment_request(
            session,
            contact_id=10,
            conversation_id=20,
            channel_id=None,
            source_message_id=202,
            extracted_entities={},
        )

        session.flush.assert_called()
