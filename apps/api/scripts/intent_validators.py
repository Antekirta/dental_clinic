"""
Sanity-check validators for the intent testing loop.

Each validator receives the test case + the actual results of running
process_incoming_message(), and returns a CheckResult(passed, name, detail).

Validators are intentionally conservative: they prefer false negatives
(missed bugs) over false positives (spurious failures), so the loop stays
useful rather than noisy.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from scripts.intent_test_cases import IntentTestCase


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


# ── DB helpers ───────────────────────────────────────────────────────────────

def _load_valid_prices(session: Session) -> set[int]:
    """Return all active service base_prices as integers (e.g. {150, 220, 280, 600})."""
    from app.db.models import Service
    rows = session.query(Service.base_price).filter(Service.is_active.is_(True)).all()
    return {int(row[0]) for row in rows if row[0] is not None}


def _load_doctor_surnames(session: Session) -> set[str]:
    """Return last-name tokens of all active doctors (e.g. {'Carter', 'Patel'})."""
    from app.db.models import Staff
    rows = (
        session.query(Staff.full_name)
        .filter(Staff.role == "doctor", Staff.is_active.is_(True))
        .all()
    )
    surnames = set()
    for (full_name,) in rows:
        parts = full_name.split()
        if parts:
            # Strip honorific prefix if present (Dr., Dr)
            tokens = [p for p in parts if not p.rstrip(".").lower() == "dr"]
            if tokens:
                surnames.add(tokens[-1])  # last token = surname
    return surnames


def _load_branch_times(session: Session) -> set[str]:
    """Return all branch open/close times as zero-padded HH:MM strings."""
    from app.db.models import BranchHour
    rows = (
        session.query(BranchHour.open_time, BranchHour.close_time)
        .filter(BranchHour.is_active.is_(True))
        .all()
    )
    times: set[str] = set()
    for open_t, close_t in rows:
        if open_t:
            times.add(open_t.strftime("%H:%M"))
        if close_t:
            times.add(close_t.strftime("%H:%M"))
    return times


# ── Text helpers ─────────────────────────────────────────────────────────────

def _has_emoji(text: str) -> bool:
    """Return True if text contains any emoji or pictograph characters."""
    for ch in text:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if (
            cat == "So"
            or (0x1F300 <= cp <= 0x1FAFF)   # Misc symbols, emoticons
            or (0x2600 <= cp <= 0x27BF)       # Misc symbols
            or (0xFE00 <= cp <= 0xFE0F)       # Variation selectors
        ):
            return True
    return False


def _count_sentences(text: str) -> int:
    """Approximate sentence count by splitting on terminal punctuation."""
    parts = re.split(r"[.!?]+", text.strip())
    return sum(1 for p in parts if p.strip())


def _extract_price_numbers(text: str) -> list[int]:
    """
    Extract numbers that appear in clear price context:
    - Preceded by a currency symbol: £220, $150
    - Followed by a currency indicator: 220 GBP, 280 руб
    - After price-related words: costs 600, стоит 150

    Conservative: ignores standalone 3-4 digit numbers to avoid false
    positives from phone numbers, years, room numbers, etc.
    """
    # Pattern A: currency symbol then number  (£220, $150, €280)
    pattern_a = r"(?:£|€|\$)\s*(\d{2,5}(?:[.,]\d{1,2})?)"
    # Pattern B: number then currency word  (220 GBP, 150 руб, 280 рублей)
    pattern_b = r"(\d{2,5}(?:[.,]\d{1,2})?)\s*(?:GBP|USD|EUR|руб(?:лей|\.)?)"
    # Pattern C: price keyword then number  (стоит 220, costs 150, price 280)
    pattern_c = r"(?:стоит|стоимость|цена|цену|price|costs?|from|за|от)\s+(\d{2,5}(?:[.,]\d{1,2})?)"

    results: list[int] = []
    for pattern in (pattern_a, pattern_b, pattern_c):
        for m in re.finditer(pattern, text, re.IGNORECASE):
            raw = m.group(1).replace(",", ".")
            try:
                results.append(int(float(raw)))
            except ValueError:
                pass
    return results


def _extract_time_patterns(text: str) -> list[str]:
    """Extract and zero-pad HH:MM patterns from text (e.g. '9:00' → '09:00')."""
    raw = re.findall(r"\b([0-2]?\d:[0-5]\d)\b", text)
    normalized = []
    for t in raw:
        parts = t.split(":")
        normalized.append(f"{int(parts[0]):02d}:{parts[1]}")
    return normalized


def _extract_doctor_refs(text: str) -> list[str]:
    """Extract surnames that follow a 'Dr.' or 'Dr' title."""
    return re.findall(r"\bDr\.?\s+([A-Z][a-z]+)", text)


# ── Individual checks ────────────────────────────────────────────────────────

def check_intent_match(classified: str | None, expected: str) -> CheckResult:
    passed = classified == expected
    detail = (
        f"got '{classified}', expected '{expected}'"
        if not passed
        else f"'{classified}'"
    )
    return CheckResult("intent_match", passed, detail)


def check_confidence(confidence: float | None, threshold: float = 0.6) -> CheckResult:
    if confidence is None:
        return CheckResult("confidence", False, "no confidence value returned")
    passed = confidence >= threshold
    detail = f"{confidence:.2f} (threshold: ≥{threshold})"
    return CheckResult("confidence", passed, detail)


def check_reply_non_empty(reply: str | None) -> CheckResult:
    passed = bool(reply and reply.strip())
    if reply and len(reply) > 70:
        detail = f'"{reply[:70]}…"'
    elif reply:
        detail = f'"{reply}"'
    else:
        detail = "reply is None or empty"
    return CheckResult("reply_non_empty", passed, detail)


def check_route_match(classified_route: str | None, expected_route: str) -> CheckResult:
    passed = classified_route == expected_route
    detail = (
        f"got '{classified_route}', expected '{expected_route}'"
        if not passed
        else f"'{classified_route}'"
    )
    return CheckResult("route_match", passed, detail)


def check_no_emoji(reply: str | None) -> CheckResult:
    if not reply:
        return CheckResult("no_emoji", True, "no reply to check")
    passed = not _has_emoji(reply)
    detail = "emoji found in reply" if not passed else "clean"
    return CheckResult("no_emoji", passed, detail)


def check_sentence_count(reply: str | None, max_sentences: int = 3) -> CheckResult:
    if not reply:
        return CheckResult("sentence_count", True, "no reply to check")
    count = _count_sentences(reply)
    passed = count <= max_sentences
    detail = f"{count} sentence(s) (max allowed: {max_sentences})"
    return CheckResult("sentence_count", passed, detail)


def check_prices_valid(reply: str | None, session: Session) -> CheckResult:
    """
    Verify that any prices mentioned in the reply exist in the DB.
    Only checks numbers that appear in clear price context (£220, стоит 150, etc.)
    to avoid false positives from addresses, phone numbers, or years.
    """
    if not reply:
        return CheckResult("prices_valid", True, "no reply to check")

    numbers = _extract_price_numbers(reply)
    if not numbers:
        return CheckResult("prices_valid", True, "no price figures found in reply")

    valid_prices = _load_valid_prices(session)
    invalid = [n for n in numbers if n not in valid_prices]

    if invalid:
        return CheckResult(
            "prices_valid",
            False,
            f"mentioned {invalid} — not in DB service prices {sorted(valid_prices)}",
        )
    return CheckResult("prices_valid", True, f"all prices match DB: {sorted(set(numbers))}")


def check_doctors_valid(reply: str | None, session: Session) -> CheckResult:
    """
    Verify that any 'Dr. Surname' references in the reply match real DB doctors.
    Only matches English-format names; Russian-language replies without 'Dr.' pass.
    """
    if not reply:
        return CheckResult("doctors_valid", True, "no reply to check")

    mentioned = _extract_doctor_refs(reply)
    if not mentioned:
        return CheckResult("doctors_valid", True, "no 'Dr. Surname' patterns found")

    db_surnames = _load_doctor_surnames(session)
    invalid = [name for name in mentioned if name not in db_surnames]

    if invalid:
        return CheckResult(
            "doctors_valid",
            False,
            f"unknown doctor surname(s): {invalid} (DB has: {sorted(db_surnames)})",
        )
    return CheckResult("doctors_valid", True, f"all doctor refs valid: {mentioned}")


def check_hours_valid(reply: str | None, session: Session) -> CheckResult:
    """
    Verify that any HH:MM times in the reply match real DB branch opening/closing times.
    """
    if not reply:
        return CheckResult("hours_valid", True, "no reply to check")

    times = _extract_time_patterns(reply)
    if not times:
        return CheckResult("hours_valid", True, "no HH:MM patterns found")

    valid_times = _load_branch_times(session)
    invalid = [t for t in times if t not in valid_times]

    if invalid:
        return CheckResult(
            "hours_valid",
            False,
            f"times {invalid} not found in DB branch hours (valid: {sorted(valid_times)})",
        )
    return CheckResult("hours_valid", True, f"all times match DB: {sorted(set(times))}")


def check_booking_asks_one_field(reply: str | None) -> CheckResult:
    """
    For booking intents, verify the bot asks for at most one missing field at a time.
    Looks for field-keyword clusters in both English and Russian.
    """
    if not reply:
        return CheckResult("booking_asks_one_field", True, "no reply to check")

    reply_lower = reply.lower()

    field_keywords: dict[str, list[str]] = {
        "service":  ["service", "услуг", "процедур", "лечени", "чистк", "отбелив"],
        "date":     ["date", "day", "when", "дат", "день", "когда", "числ", "время"],
        "phone":    ["phone", "number", "телефон", "номер"],
        "name":     ["your name", "как вас зовут", "назовите", "ваше имя"],
    }

    fields_detected = [
        field_name
        for field_name, keywords in field_keywords.items()
        if any(kw in reply_lower for kw in keywords)
    ]

    passed = len(fields_detected) <= 1
    if fields_detected:
        detail = f"detected field references: {fields_detected}"
    else:
        detail = "no specific booking field detected in reply"
    return CheckResult("booking_asks_one_field", passed, detail)


# ── Dispatcher ───────────────────────────────────────────────────────────────

_CHECKER_MAP = {
    "intent_match":          lambda tc, classified_intent, **kw: check_intent_match(classified_intent, tc.expected_intent),
    "confidence":            lambda tc, confidence, **kw: check_confidence(confidence),
    "reply_non_empty":       lambda tc, reply_text, **kw: check_reply_non_empty(reply_text),
    "route_match":           lambda tc, classified_route, **kw: check_route_match(classified_route, tc.expected_route),
    "no_emoji":              lambda tc, reply_text, **kw: check_no_emoji(reply_text),
    "sentence_count":        lambda tc, reply_text, **kw: check_sentence_count(reply_text),
    "prices_valid":          lambda tc, reply_text, session, **kw: check_prices_valid(reply_text, session),
    "doctors_valid":         lambda tc, reply_text, session, **kw: check_doctors_valid(reply_text, session),
    "hours_valid":           lambda tc, reply_text, session, **kw: check_hours_valid(reply_text, session),
    "booking_asks_one_field": lambda tc, reply_text, **kw: check_booking_asks_one_field(reply_text),
}


def run_checks(
    tc: "IntentTestCase",
    classified_intent: str | None,
    classified_route: str | None,
    confidence: float | None,
    reply_text: str | None,
    session: Session,
) -> list[CheckResult]:
    """Run all checks listed in tc.checks and return results."""
    results: list[CheckResult] = []
    for check_name in tc.checks:
        fn = _CHECKER_MAP.get(check_name)
        if fn is None:
            results.append(CheckResult(check_name, False, f"unknown checker: '{check_name}'"))
            continue
        try:
            result = fn(
                tc=tc,
                classified_intent=classified_intent,
                classified_route=classified_route,
                confidence=confidence,
                reply_text=reply_text,
                session=session,
            )
            results.append(result)
        except Exception as exc:
            results.append(CheckResult(check_name, False, f"checker raised {type(exc).__name__}: {exc}"))
    return results
