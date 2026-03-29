"""
Test case definitions for the intent testing loop.

One representative message per intent — messages are in Russian
to reflect the primary language of the clinic's patient base.
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
        message="Здравствуйте! Как дела?",
        expected_intent="greeting",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Basic greeting from a new patient",
    ),
    IntentTestCase(
        intent_code="price_question",
        message="Сколько стоит чистка зубов? И сколько стоит консультация?",
        expected_intent="price_question",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "prices_valid"],
        description="Price inquiry for dental services",
    ),
    IntentTestCase(
        intent_code="service_info",
        message="Расскажите подробнее об ортодонтической оценке — что это включает?",
        expected_intent="service_info",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Request for service details",
    ),
    IntentTestCase(
        intent_code="appointment_request",
        message="Хочу записаться к стоматологу на чистку зубов",
        expected_intent="appointment_request",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "booking_asks_one_field"],
        description="Appointment booking request",
    ),
    IntentTestCase(
        intent_code="appointment_availability",
        message="Есть ли свободные слоты на следующей неделе для консультации?",
        expected_intent="appointment_availability",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Check appointment availability",
    ),
    IntentTestCase(
        intent_code="emergency",
        message="После удаления зуба сильное кровотечение и опухоль, мне очень больно, помогите срочно!",
        expected_intent="emergency",
        expected_route="handoff_urgent",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match"],
        description="Dental emergency",
    ),
    IntentTestCase(
        intent_code="clinic_hours",
        message="В какие часы работает ваша клиника? Работаете ли вы в субботу?",
        expected_intent="clinic_hours",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match", "hours_valid"],
        description="Clinic working hours inquiry",
    ),
    IntentTestCase(
        intent_code="location_question",
        message="Где находится ваша клиника? Как к вам добраться на метро?",
        expected_intent="location_question",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Location and directions inquiry",
    ),
    IntentTestCase(
        intent_code="doctor_question",
        message="Какие у вас есть врачи? Есть ли специалист по ортодонтии?",
        expected_intent="doctor_question",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match", "doctors_valid"],
        description="Inquiry about available doctors",
    ),
    IntentTestCase(
        intent_code="insurance_or_documents",
        message="Вы принимаете страховку BUPA? Мне нужно узнать о страховом покрытии.",
        expected_intent="insurance_or_documents",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Insurance and documents inquiry",
    ),
    IntentTestCase(
        intent_code="first_visit_question",
        message="Я первый раз обращаюсь к стоматологу, что нужно взять с собой и чего ожидать?",
        expected_intent="first_visit_question",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="First visit guidance",
    ),
    IntentTestCase(
        intent_code="promotion_interest",
        message="У вас есть специальные предложения или скидки для новых пациентов?",
        expected_intent="promotion_interest",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Promotions and discounts inquiry",
    ),

    # ── Existing patient intents ────────────────────────────────────────────
    IntentTestCase(
        intent_code="reschedule_appointment",
        message="Мне нужно перенести запись на другой день, у меня изменились планы",
        expected_intent="reschedule_appointment",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment reschedule request",
    ),
    IntentTestCase(
        intent_code="cancel_appointment",
        message="Хочу отменить свою запись на приём к врачу",
        expected_intent="cancel_appointment",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment cancellation request",
    ),
    IntentTestCase(
        intent_code="confirm_appointment",
        message="Да, подтверждаю свой визит в пятницу в 11:00",
        expected_intent="confirm_appointment",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment confirmation",
    ),
    IntentTestCase(
        intent_code="appointment_details",
        message="Скажите, в какое время у меня назначен следующий приём и к какому врачу?",
        expected_intent="appointment_details",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        has_active_appointment=True,
        description="Appointment details inquiry",
    ),
    IntentTestCase(
        intent_code="post_visit_followup",
        message="Я был у вас вчера, после лечения у меня ноет зуб — это нормально?",
        expected_intent="post_visit_followup",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Post-visit follow-up question",
    ),
    IntentTestCase(
        intent_code="treatment_plan_question",
        message="Доктор упоминал план лечения, можно получить его в письменном виде?",
        expected_intent="treatment_plan_question",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Treatment plan inquiry",
    ),
    IntentTestCase(
        intent_code="repeat_service_request",
        message="Хочу снова записаться на профессиональную чистку зубов как в прошлый раз",
        expected_intent="repeat_service_request",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match", "booking_asks_one_field"],
        is_existing_patient=True,
        description="Repeat service booking",
    ),
    IntentTestCase(
        intent_code="results_or_records_request",
        message="Пришлите мне результаты рентгена и справку о лечении на email",
        expected_intent="results_or_records_request",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        is_existing_patient=True,
        description="Medical records request",
    ),

    # ── Universal intents ────────────────────────────────────────────────────
    IntentTestCase(
        intent_code="contact_request",
        message="Можно мне поговорить с администратором или менеджером клиники?",
        expected_intent="contact_request",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Request to speak with staff",
    ),
    IntentTestCase(
        intent_code="leave_contact",
        message="Мой номер телефона +44 7700 900999, свяжитесь со мной пожалуйста",
        expected_intent="leave_contact",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Patient leaves their contact details",
    ),
    IntentTestCase(
        intent_code="provide_booking_data",
        message="Хочу на вторник 15 апреля в 10:00 утра. Меня зовут Анна.",
        expected_intent="provide_booking_data",
        expected_route="auto_reply_and_collect",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "route_match"],
        description="Patient provides booking details",
    ),
    IntentTestCase(
        intent_code="faq_general",
        message="Вы лечите детей? Принимаете ли пациентов без предварительной записи?",
        expected_intent="faq_general",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="General FAQ",
    ),
    IntentTestCase(
        intent_code="complaint_or_negative_feedback",
        message="Я очень недоволен вашим обслуживанием, пришлось ждать полтора часа, это неприемлемо",
        expected_intent="complaint_or_negative_feedback",
        expected_route="handoff_admin",
        checks=["intent_match", "confidence", "reply_non_empty", "route_match"],
        description="Patient complaint",
    ),
    IntentTestCase(
        intent_code="gratitude_or_positive_feedback",
        message="Огромное спасибо за отличное обслуживание! Врач был очень профессиональным.",
        expected_intent="gratitude_or_positive_feedback",
        expected_route="auto_reply",
        checks=["intent_match", "confidence", "reply_non_empty", "no_emoji", "sentence_count", "route_match"],
        description="Positive feedback",
    ),
    IntentTestCase(
        intent_code="non_relevant_message",
        message="Посоветуйте хороший фильм для просмотра на вечер",
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
