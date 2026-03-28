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

import google.generativeai as genai

from app.config import settings
from app.modules.inbound_messages.constants import (
    INTENT_ROUTE_MAP,
    IntentCode,
    RouteType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SDK initialisation (lazy — runs on first import)
# ---------------------------------------------------------------------------
genai.configure(api_key=settings.gemini_api_key)

_model = genai.GenerativeModel(settings.gemini_model)


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
Ты — AI-классификатор сообщений стоматологической клиники BrightSmile Dental Clinic.

Твоя задача: получить сообщение пациента (или потенциального клиента) и определить:
1. intent_code — основное намерение из списка ниже
2. confidence — уверенность от 0.0 до 1.0
3. extracted_entities — извлечённые данные (если есть)

Если в сообщении несколько намерений, выбери главное для маршрутизации.
Извлечённые сущности сохрани все, даже если они относятся к другому intent.

Допустимые intent_code:
- greeting — приветствие без конкретного запроса
- price_question — вопрос о стоимости
- service_info — вопрос о содержании услуги
- appointment_request — хочет записаться
- appointment_availability — уточняет доступное время
- emergency — срочная боль, травма, отёк
- clinic_hours — график работы
- location_question — адрес, парковка, как добраться
- doctor_question — вопрос о враче или специализации
- insurance_or_documents — страховка, документы, справки
- first_visit_question — вопрос о первом визите
- promotion_interest — акция, промо, спецпредложение
- reschedule_appointment — перенос записи
- cancel_appointment — отмена записи
- confirm_appointment — подтверждение записи
- appointment_details — уточнение деталей записи
- post_visit_followup — вопрос после лечения
- treatment_plan_question — продолжение лечения
- repeat_service_request — повторная запись на знакомую услугу
- results_or_records_request — запрос снимков, выписок
- contact_request — просьба позвонить, связать с администратором
- leave_contact — оставляет номер или email
- provide_booking_data — присылает данные для записи (имя, телефон, дату и т.д.)
- faq_general — общий вопрос о клинике
- complaint_or_negative_feedback — жалоба, недовольство
- gratitude_or_positive_feedback — благодарность, положительный отзыв
- non_relevant_message — спам, не по теме
- unknown — невозможно определить intent

Извлекаемые сущности (extracted_entities):
- name — имя пациента
- phone — телефон
- email — email
- service — название услуги
- date_preference — желаемая дата (как текст, например "завтра", "суббота", "15 апреля")
- time_preference — желаемое время ("утром", "после 18:00", "вечером")
- doctor_preference — имя или специализация врача
- promotion_name — название акции

Если сущность не найдена, НЕ включай её в extracted_entities — оставь поле пустым.

ВАЖНО: Отвечай ТОЛЬКО валидным JSON объектом без пояснений.
"""

_REPLY_GENERATION_SYSTEM_PROMPT = """\
Ты — вежливый и краткий чат-бот стоматологической клиники BrightSmile Dental Clinic.

Правила ответа:
1. Будь кратким — 1-3 предложения.
2. Не давай медицинских советов и не ставь диагнозов.
3. После ответа предложи ОДИН конкретный следующий шаг.
4. Если собираешь данные для записи, спроси только ОДНО недостающее поле за раз.
5. Пиши на том языке, на котором написал пациент (обычно русский).
6. Не используй эмодзи.
7. Не повторяй приветствие, если в истории уже есть приветствие от бота.

Тон: дружелюбный, профессиональный, без лишних слов.

ВАЖНО: Отвечай ТОЛЬКО текстом ответа пациенту, без JSON, без пояснений.
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
        ctx_lines = ["Контекст контакта:"]
        if contact_context.name:
            ctx_lines.append(f"  Имя: {contact_context.name}")
        if contact_context.phone:
            ctx_lines.append(f"  Телефон: {contact_context.phone}")
        if contact_context.is_existing_patient:
            ctx_lines.append("  Тип: действующий пациент")
        else:
            ctx_lines.append("  Тип: новый контакт")
        if contact_context.has_active_appointment:
            ctx_lines.append("  Есть активная запись: да")
        parts.append("\n".join(ctx_lines))

    if conversation_history:
        history_lines = ["История диалога (последние сообщения):"]
        for turn in conversation_history[-10:]:  # max 10 recent turns
            label = {"contact": "Пациент", "bot": "Бот", "staff": "Администратор"}.get(
                turn.role, turn.role
            )
            history_lines.append(f"  {label}: {turn.text}")
        parts.append("\n".join(history_lines))

    parts.append(f"Новое сообщение пациента:\n{text}")

    user_prompt = "\n\n".join(parts)

    # Call Gemini
    try:
        response = _model.generate_content(
            [
                {"role": "user", "parts": [_CLASSIFICATION_SYSTEM_PROMPT + "\n\n" + user_prompt]},
            ],
            generation_config=genai.GenerationConfig(
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
        logger.warning("Gemini returned unknown intent_code='%s', falling back to 'unknown'", intent_code)
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
    """
    parts: list[str] = []

    # Intent context
    parts.append(f"Определённый intent: {intent_code}")

    # What was extracted
    if extracted_entities:
        ent_lines = ["Извлечённые данные:"]
        for k, v in extracted_entities.items():
            ent_lines.append(f"  {k}: {v}")
        parts.append("\n".join(ent_lines))

    # What's still missing (for booking flows)
    if missing_fields:
        parts.append(f"Недостающие данные для записи: {', '.join(missing_fields)}")

    # Reference data (prices, hours, location, etc.)
    if reference_data:
        ref_lines = ["Справочные данные клиники:"]
        for k, v in reference_data.items():
            ref_lines.append(f"  {k}: {v}")
        parts.append("\n".join(ref_lines))

    # Conversation history
    if conversation_history:
        history_lines = ["История диалога:"]
        for turn in conversation_history[-10:]:
            label = {"contact": "Пациент", "bot": "Бот", "staff": "Администратор"}.get(
                turn.role, turn.role
            )
            history_lines.append(f"  {label}: {turn.text}")
        parts.append("\n".join(history_lines))

    parts.append("Сгенерируй ответ пациенту.")

    user_prompt = "\n\n".join(parts)

    try:
        response = _model.generate_content(
            [
                {"role": "user", "parts": [_REPLY_GENERATION_SYSTEM_PROMPT + "\n\n" + user_prompt]},
            ],
            generation_config=genai.GenerationConfig(
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
