"""
Test case definitions for the intent testing loop.

One representative message per intent.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IntentTestCase:
    intent_code: str
    message: str
    expected_intent: str
    expected_route: str
    checks: list[str]
    is_existing_patient: bool = False
    has_active_appointment: bool = False
    description: str = ""


INTENT_TEST_CASES: list[IntentTestCase] = [
    # ── New client intents ──────────────────────────────────────────────────
    IntentTestCase(
        intent_code="greeting",
        message="Hello! How are you?",
        expected_intent="greeting",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Basic greeting from a new patient",
    ),
    IntentTestCase(
        intent_code="price_question",
        message="How much does a dental cleaning cost? And what is the price for an initial consultation?",
        expected_intent="price_question",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "prices_valid"],
        description="Price inquiry for dental services",
    ),
    IntentTestCase(
        intent_code="service_info",
        message="Can you tell me more about the orthodontic evaluation? What does it include?",
        expected_intent="service_info",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Request for service details",
    ),
    IntentTestCase(
        intent_code="appointment_request",
        message="I would like to book an appointment for a dental cleaning.",
        expected_intent="appointment_request",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "booking_asks_one_field"],
        description="Appointment booking request",
    ),
    IntentTestCase(
        intent_code="appointment_availability",
        message="Do you have any free slots next week for a consultation?",
        expected_intent="appointment_availability",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Check appointment availability",
    ),
    IntentTestCase(
        intent_code="emergency",
        message="I had a tooth extracted yesterday and now I have severe bleeding and swelling, please help urgently!",
        expected_intent="emergency",
        expected_route="handoff_urgent",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match"],
        description="Dental emergency",
    ),
    IntentTestCase(
        intent_code="clinic_hours",
        message="What are your opening hours? Do you work on Saturdays?",
        expected_intent="clinic_hours",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match", "hours_valid"],
        description="Clinic working hours inquiry",
    ),
    IntentTestCase(
        intent_code="location_question",
        message="Where is your clinic located? How do I get there by tube?",
        expected_intent="location_question",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Location and directions inquiry",
    ),
    IntentTestCase(
        intent_code="doctor_question",
        message="What doctors do you have? Is there an orthodontics specialist?",
        expected_intent="doctor_question",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "doctors_valid"],
        description="Inquiry about available doctors",
    ),
    IntentTestCase(
        intent_code="insurance_or_documents",
        message="Do you accept BUPA insurance? I need to know about my coverage.",
        expected_intent="insurance_or_documents",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Insurance and documents inquiry",
    ),
    IntentTestCase(
        intent_code="first_visit_question",
        message="This is my first time visiting a dentist. What should I bring and what should I expect?",
        expected_intent="first_visit_question",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="First visit guidance",
    ),
    IntentTestCase(
        intent_code="promotion_interest",
        message="Do you have any special offers or discounts for new patients?",
        expected_intent="promotion_interest",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Promotions and discounts inquiry",
    ),

    # ── Existing patient intents ────────────────────────────────────────────
    IntentTestCase(
        intent_code="reschedule_appointment",
        message="I need to move my appointment to a different day, my plans have changed.",
        expected_intent="reschedule_appointment",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment reschedule request",
    ),
    IntentTestCase(
        intent_code="cancel_appointment",
        message="I would like to cancel my upcoming appointment.",
        expected_intent="cancel_appointment",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment cancellation request",
    ),
    IntentTestCase(
        intent_code="confirm_appointment",
        message="Yes, I confirm my visit on Friday at 11:00.",
        expected_intent="confirm_appointment",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment confirmation",
    ),
    IntentTestCase(
        intent_code="appointment_details",
        message="Can you tell me what time my next appointment is and which doctor I am seeing?",
        expected_intent="appointment_details",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment details inquiry",
    ),
    IntentTestCase(
        intent_code="post_visit_followup",
        message="I was at your clinic yesterday and now my tooth is aching. Is that normal?",
        expected_intent="post_visit_followup",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Post-visit follow-up question",
    ),
    IntentTestCase(
        intent_code="treatment_plan_question",
        message="The doctor mentioned a treatment plan. Can I get it in writing?",
        expected_intent="treatment_plan_question",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Treatment plan inquiry",
    ),
    IntentTestCase(
        intent_code="repeat_service_request",
        message="I would like to book another dental cleaning like I had last time.",
        expected_intent="repeat_service_request",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match", "booking_asks_one_field"],
        is_existing_patient=True,
        description="Repeat service booking",
    ),
    IntentTestCase(
        intent_code="results_or_records_request",
        message="Please send my X-ray results and treatment summary to my email.",
        expected_intent="results_or_records_request",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Medical records request",
    ),

    # ── Universal intents ────────────────────────────────────────────────────
    IntentTestCase(
        intent_code="contact_request",
        message="Can I speak with an administrator or a clinic manager please?",
        expected_intent="contact_request",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Request to speak with staff",
    ),
    IntentTestCase(
        intent_code="leave_contact",
        message="My phone number is +44 7700 900999, please get in touch with me.",
        expected_intent="leave_contact",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Patient leaves their contact details",
    ),
    IntentTestCase(
        intent_code="provide_booking_data",
        message="I want Tuesday 15 April at 10:00 am. My name is Anna.",
        expected_intent="provide_booking_data",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match"],
        description="Patient provides booking details",
    ),
    IntentTestCase(
        intent_code="faq_general",
        message="Do you treat children? Can I come in without a prior appointment?",
        expected_intent="faq_general",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="General FAQ",
    ),
    IntentTestCase(
        intent_code="complaint_or_negative_feedback",
        message="I am very unhappy with your service. I had to wait over an hour. This is unacceptable.",
        expected_intent="complaint_or_negative_feedback",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Patient complaint",
    ),
    IntentTestCase(
        intent_code="gratitude_or_positive_feedback",
        message="Thank you so much for the excellent service! The doctor was very professional.",
        expected_intent="gratitude_or_positive_feedback",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Positive feedback",
    ),
    IntentTestCase(
        intent_code="non_relevant_message",
        message="Can you recommend a good movie to watch tonight?",
        expected_intent="non_relevant_message",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Off-topic message unrelated to dentistry",
    ),
    IntentTestCase(
        intent_code="unknown",
        message="xkcd 42 foobar ??? !!!",
        expected_intent="unknown",
        expected_route="auto_reply_and_collect",
        checks=["reply_non_empty"],
        description="Gibberish / unclassifiable message — only verifies a reply is sent",
    ),
]
