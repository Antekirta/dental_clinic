"""
Gemini AI integration for intent classification and reply generation.

Two-call design:
  Call 1 — classify_message():  text + history → intent, route, confidence, entities
  Call 2 — generate_reply():    intent + entities + context + reference data → reply text

Both calls use structured JSON output via response_schema so we never need
to parse free-form LLM text.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.modules.inbound_messages.constants import (
    INTENT_ROUTE_MAP,
    IntentCode,
    RouteType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SDK initialisation — deferred to first use so tests can mock before calling
# ---------------------------------------------------------------------------
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return the shared client instance, initialising it on first call."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ClassificationResult:
    """Structured output of the classification call."""

    intent_code: str
    route_type: str
    confidence: float
    extracted_entities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurn:
    """One message in conversation history."""

    role: str  # "contact" | "bot" | "staff"
    text: str


@dataclass
class ContactContext:
    """What we already know about the contact."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_existing_patient: bool = False
    has_active_appointment: bool = False


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
_CLASSIFICATION_SYSTEM_PROMPT = """\
You are an AI message classifier for BrightSmile Dental Clinic.

Your task: given a patient (or prospective patient) message, determine:
1. intent_code — the primary intent from the list below
2. confidence — confidence score from 0.0 to 1.0
3. extracted_entities — any data extracted from the message

If the message contains multiple intents, pick the primary one for routing.
Extract all entities regardless of which intent they relate to.

Allowed intent_code values:
- greeting — greeting with no specific request
- price_question — asking about cost or pricing
- service_info — asking what a service includes or how it works
- appointment_request — wants to book an appointment
- appointment_availability — asking about available dates/times
- emergency — urgent pain, injury, swelling
- clinic_hours — asking about working hours
- location_question — asking about address, parking, directions
- doctor_question — asking about a specific doctor or specialty
- insurance_or_documents — insurance, documents, certificates
- first_visit_question — asking about what to expect on first visit
- promotion_interest — asking about a promotion or special offer
- reschedule_appointment — wants to reschedule an existing appointment
- cancel_appointment — wants to cancel an appointment
- confirm_appointment — confirming an appointment
- appointment_details — asking about details of an existing appointment
- post_visit_followup — question after treatment
- treatment_plan_question — asking about continuing treatment
- repeat_service_request — wants to book a familiar service again
- results_or_records_request — requesting X-rays, records, reports
- contact_request — asking to be called back or connected to admin
- leave_contact — providing phone number or email for callback
- provide_booking_data — providing data needed for booking (name, phone, date, etc.)
- faq_general — general question about the clinic
- complaint_or_negative_feedback — complaint or dissatisfaction
- gratitude_or_positive_feedback — thanks or positive feedback
- non_relevant_message — spam, off-topic
- unknown — intent cannot be determined

Extractable entities (extracted_entities):
- name — patient's name
- phone — phone number
- email — email address
- service — name of the service
- date_preference — preferred date (as text, e.g. "tomorrow", "Saturday", "April 15")
- time_preference — preferred time (e.g. "morning", "after 6pm", "evening")
- doctor_preference — doctor name or specialty
- promotion_name — name of the promotion

If an entity is not found, do NOT include it in extracted_entities.

IMPORTANT: Respond ONLY with a valid JSON object, no explanations.
"""

_REPLY_GENERATION_SYSTEM_PROMPT = """\
You are a friendly and concise chatbot for BrightSmile Dental Clinic.

Reply rules:
1. Be brief — 1-3 sentences.
2. Do not give medical advice or diagnose conditions.
3. After answering, suggest ONE clear next step.
4. When collecting booking data, ask for only ONE missing field at a time.
5. Reply in the same language the patient used.
6. Do not use emoji.
7. Do not repeat a greeting if the conversation history already contains one from the bot.
8. Base your reply strictly on the classified intent and the patient's last message. Do not repeat or volunteer information from prior bot replies unless the patient explicitly asked for it again.
9. If the clinic reference data contains multiple branches, include information for ALL of them in your reply. Never omit a branch. If the patient has not specified a branch, ask which branch they are asking about OR list the information for all branches.

Tone: friendly, professional, no filler words.

IMPORTANT: Respond ONLY with the reply text to the patient. No JSON, no explanations.
"""


# ---------------------------------------------------------------------------
# Classification call (Call 1)
# ---------------------------------------------------------------------------
def classify_message(
    text: str,
    conversation_history: list[ConversationTurn],
    contact_context: ContactContext | None = None,
) -> ClassificationResult:
    """
    Call Gemini to classify the incoming message.

    Returns a ClassificationResult with intent_code, route_type (looked up
    from INTENT_ROUTE_MAP), confidence, and extracted_entities.
    """
    # Build the user prompt with context
    parts: list[str] = []

    if contact_context:
        ctx_lines = ["Contact context:"]
        if contact_context.name:
            ctx_lines.append(f"  Name: {contact_context.name}")
        if contact_context.phone:
            ctx_lines.append(f"  Phone: {contact_context.phone}")
        if contact_context.is_existing_patient:
            ctx_lines.append("  Type: existing patient")
        else:
            ctx_lines.append("  Type: new contact")
        if contact_context.has_active_appointment:
            ctx_lines.append("  Has active appointment: yes")
        parts.append("\n".join(ctx_lines))

    if conversation_history:
        history_lines = ["Conversation history (recent messages):"]
        for turn in conversation_history[-10:]:  # max 10 recent turns
            label = {"contact": "Patient", "bot": "Bot", "staff": "Admin"}.get(
                turn.role, turn.role
            )
            history_lines.append(f"  {label}: {turn.text}")
        parts.append("\n".join(history_lines))

    parts.append(f"New patient message:\n{text}")

    user_prompt = "\n\n".join(parts)

    # Call Gemini
    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=_CLASSIFICATION_SYSTEM_PROMPT + "\n\n" + user_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "intent_code": {"type": "string"},
                        "confidence": {"type": "number"},
                        "extracted_entities": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"},
                                "service": {"type": "string"},
                                "date_preference": {"type": "string"},
                                "time_preference": {"type": "string"},
                                "doctor_preference": {"type": "string"},
                                "promotion_name": {"type": "string"},
                            },
                        },
                    },
                    "required": ["intent_code", "confidence"],
                },
                temperature=0.1,
            ),
        )

        raw = json.loads(response.text)
    except Exception:
        logger.exception("Gemini classification call failed — falling back to 'unknown'")
        return ClassificationResult(
            intent_code=IntentCode.UNKNOWN,
            route_type=RouteType.AUTO_REPLY_AND_COLLECT,
            confidence=0.0,
        )

    intent_code = raw.get("intent_code", IntentCode.UNKNOWN)
    confidence = float(raw.get("confidence", 0.0))
    entities = raw.get("extracted_entities") or {}

    # Clean empty-string values from entities
    entities = {k: v for k, v in entities.items() if v}

    # Validate intent_code — fall back to unknown if Gemini hallucinated
    if intent_code not in IntentCode.ALL:
        logger.warning(
            "Gemini returned unknown intent_code='%s', falling back to 'unknown'",
            intent_code,
        )
        intent_code = IntentCode.UNKNOWN

    # Look up route_type from the canonical map
    route_type = INTENT_ROUTE_MAP.get(intent_code, RouteType.AUTO_REPLY_AND_COLLECT)

    return ClassificationResult(
        intent_code=intent_code,
        route_type=route_type,
        confidence=confidence,
        extracted_entities=entities,
    )


# ---------------------------------------------------------------------------
# Reply generation call (Call 2)
# ---------------------------------------------------------------------------
def generate_reply(
    intent_code: str,
    extracted_entities: dict[str, Any],
    conversation_history: list[ConversationTurn],
    reference_data: dict[str, Any] | None = None,
    missing_fields: list[str] | None = None,
) -> str | None:
    """
    Call Gemini to generate a reply to the patient.

    Only called for auto_reply and auto_reply_and_collect routes.
    Returns the reply text, or None if the call fails.

    Uses native multi-turn contents so Gemini treats the history as actual
    conversation context rather than few-shot examples.  Per-message context
    (intent, reference data) goes into system_instruction so it cannot be
    overridden by history patterns.
    """
    # Build system instruction: static rules + per-message context
    sys_parts = [_REPLY_GENERATION_SYSTEM_PROMPT, f"\nCurrent message intent: {intent_code}"]

    if extracted_entities:
        ent_lines = ["Extracted entities:"]
        for k, v in extracted_entities.items():
            ent_lines.append(f"  {k}: {v}")
        sys_parts.append("\n".join(ent_lines))

    if missing_fields:
        sys_parts.append(f"Missing booking fields: {', '.join(missing_fields)}")

    if reference_data:
        ref_lines = ["Clinic reference data:"]
        for k, v in reference_data.items():
            ref_lines.append(f"  {k}: {v}")
        sys_parts.append("\n".join(ref_lines))

    sys_parts.append(
        f"Respond to the patient's '{intent_code}' message only. "
        "Do not bring up topics not present in the patient's last message."
    )

    system_instruction = "\n\n".join(sys_parts)

    # Build multi-turn contents from conversation history.
    # contact → "user", bot/staff → "model"
    role_map = {"contact": "user", "bot": "model", "staff": "model"}
    raw_turns = conversation_history[-10:]

    # Merge consecutive same-role turns (can happen at history boundaries)
    merged: list[tuple[str, str]] = []
    for turn in raw_turns:
        role = role_map.get(turn.role, "user")
        if merged and merged[-1][0] == role:
            merged[-1] = (role, merged[-1][1] + "\n" + turn.text)
        else:
            merged.append((role, turn.text))

    # Gemini requires turns to start with "user"
    if merged and merged[0][0] == "model":
        merged.insert(0, ("user", "(conversation start)"))

    # Gemini requires turns to end with "user"
    if not merged or merged[-1][0] == "model":
        merged.append(("user", "(please respond)"))

    contents = [
        types.Content(role=role, parts=[types.Part(text=text)])
        for role, text in merged
    ]

    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
                max_output_tokens=500,
            ),
        )
        reply = response.text.strip()
        if not reply:
            logger.warning("Gemini returned empty reply for intent=%s", intent_code)
            return None
        return reply

    except Exception:
        logger.exception("Gemini reply generation failed for intent=%s", intent_code)
        return None
