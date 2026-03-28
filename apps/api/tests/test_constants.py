"""
Unit tests for constants.py — verifies integrity and consistency of the
intent taxonomy, route map, and related constants.
"""
from __future__ import annotations

from app.modules.inbound_messages.constants import (
    INTENT_ROUTE_MAP,
    AppointmentRequestStatus,
    ConversationStatusCode,
    HandoffTaskType,
    IntentCode,
    Priority,
    RouteType,
)


# ---------------------------------------------------------------------------
# IntentCode
# ---------------------------------------------------------------------------

class TestIntentCode:

    def test_all_contains_exactly_28_intents(self):
        assert len(IntentCode.ALL) == 28

    def test_mvp_is_subset_of_all(self):
        assert IntentCode.MVP.issubset(IntentCode.ALL)

    def test_unknown_in_all(self):
        assert IntentCode.UNKNOWN in IntentCode.ALL

    def test_greeting_in_all(self):
        assert IntentCode.GREETING in IntentCode.ALL

    def test_no_duplicate_values(self):
        """Each intent code string must be unique."""
        values = [
            getattr(IntentCode, attr)
            for attr in dir(IntentCode)
            if not attr.startswith("_") and attr not in ("ALL", "MVP")
        ]
        assert len(values) == len(set(values))

    def test_all_class_attrs_in_all_set(self):
        """Every string constant on IntentCode must be in ALL."""
        for attr in dir(IntentCode):
            if attr.startswith("_") or attr in ("ALL", "MVP"):
                continue
            val = getattr(IntentCode, attr)
            if isinstance(val, str):
                assert val in IntentCode.ALL, f"{attr}={val!r} not in IntentCode.ALL"


# ---------------------------------------------------------------------------
# RouteType
# ---------------------------------------------------------------------------

class TestRouteType:

    def test_all_contains_5_routes(self):
        assert len(RouteType.ALL) == 5

    def test_known_routes(self):
        assert RouteType.AUTO_REPLY in RouteType.ALL
        assert RouteType.AUTO_REPLY_AND_COLLECT in RouteType.ALL
        assert RouteType.HANDOFF_ADMIN in RouteType.ALL
        assert RouteType.HANDOFF_URGENT in RouteType.ALL
        assert RouteType.SILENT_IGNORE in RouteType.ALL


# ---------------------------------------------------------------------------
# INTENT_ROUTE_MAP
# ---------------------------------------------------------------------------

class TestIntentRouteMap:

    def test_every_intent_has_a_route(self):
        """Every intent in IntentCode.ALL must have a route mapping."""
        for intent in IntentCode.ALL:
            assert intent in INTENT_ROUTE_MAP, f"Missing route for {intent!r}"

    def test_no_extra_intents_in_map(self):
        """Route map should not contain intents outside the taxonomy."""
        for intent in INTENT_ROUTE_MAP:
            assert intent in IntentCode.ALL, f"Extra intent in map: {intent!r}"

    def test_all_routes_are_valid(self):
        """Every route type value in the map must be in RouteType.ALL."""
        for intent, route in INTENT_ROUTE_MAP.items():
            assert route in RouteType.ALL, f"{intent} maps to invalid route {route!r}"

    def test_emergency_routes_to_handoff_urgent(self):
        assert INTENT_ROUTE_MAP[IntentCode.EMERGENCY] == RouteType.HANDOFF_URGENT

    def test_greeting_routes_to_auto_reply(self):
        assert INTENT_ROUTE_MAP[IntentCode.GREETING] == RouteType.AUTO_REPLY

    def test_appointment_request_routes_to_auto_reply_and_collect(self):
        assert INTENT_ROUTE_MAP[IntentCode.APPOINTMENT_REQUEST] == RouteType.AUTO_REPLY_AND_COLLECT

    def test_complaint_routes_to_handoff_admin(self):
        assert INTENT_ROUTE_MAP[IntentCode.COMPLAINT_OR_NEGATIVE_FEEDBACK] == RouteType.HANDOFF_ADMIN


# ---------------------------------------------------------------------------
# Other constant classes — basic sanity
# ---------------------------------------------------------------------------

class TestConversationStatusCode:

    def test_has_new_incoming(self):
        assert ConversationStatusCode.NEW_INCOMING == "new_incoming"

    def test_has_classified(self):
        assert ConversationStatusCode.CLASSIFIED == "classified"

    def test_has_urgent_handoff(self):
        assert ConversationStatusCode.URGENT_HANDOFF == "urgent_handoff"


class TestAppointmentRequestStatus:

    def test_lifecycle_order(self):
        """Statuses represent a lifecycle — verify key values exist."""
        assert AppointmentRequestStatus.NEW == "new"
        assert AppointmentRequestStatus.COLLECTING_DATA == "collecting_data"
        assert AppointmentRequestStatus.PENDING_ADMIN == "pending_admin"
        assert AppointmentRequestStatus.CONVERTED == "converted"
        assert AppointmentRequestStatus.CANCELLED == "cancelled"


class TestHandoffTaskType:

    def test_has_urgent_case(self):
        assert HandoffTaskType.URGENT_CASE == "urgent_case"

    def test_has_complaint(self):
        assert HandoffTaskType.COMPLAINT == "complaint"

    def test_all_9_types(self):
        types = [
            getattr(HandoffTaskType, attr)
            for attr in dir(HandoffTaskType)
            if not attr.startswith("_")
        ]
        assert len(types) == 9


class TestPriority:

    def test_values(self):
        assert Priority.LOW == "low"
        assert Priority.NORMAL == "normal"
        assert Priority.HIGH == "high"
        assert Priority.URGENT == "urgent"
