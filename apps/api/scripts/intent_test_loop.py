#!/usr/bin/env python3
"""
Intent testing loop for BrightSmile chatbot.

Tests all 28 intents end-to-end using the real Gemini API and local database.
Telegram sends are mocked so no real messages are dispatched.
Each test runs in a DB transaction that is rolled back afterwards — no
test data is permanently written to the database.

Usage:
    python scripts/intent_test_loop.py                    # run all 28 intents
    python scripts/intent_test_loop.py --intent greeting  # run one intent
    python scripts/intent_test_loop.py --verbose          # print full reply text
    python scripts/intent_test_loop.py --fail-fast        # stop after first failure
    python scripts/intent_test_loop.py --no-rollback      # keep test rows (for debugging)
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

# Ensure stdout/stderr can handle Unicode box-drawing and Cyrillic characters
# regardless of the terminal's default encoding (e.g. cp1251 on Windows).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, io.UnsupportedOperation):
        pass

# Allow sibling imports from the scripts directory
sys.path.insert(0, str(Path(__file__).parent))

from intent_test_cases import INTENT_TEST_CASES, IntentTestCase  # noqa: E402
from intent_validators import CheckResult, run_checks  # noqa: E402

from app.db.models import ConversationIntent  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.inbound_messages.schemas import (  # noqa: E402
    ChannelPayload,
    ContactMatchKeysPayload,
    ContactPayload,
    ConversationPayload,
    EventPayload,
    MessagePayload,
    SourceMetadataPayload,
    UnifiedIncomingMessage,
)
from app.modules.inbound_messages.service import process_incoming_message  # noqa: E402


# ── ANSI colours ─────────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_LINE   = "━" * 58


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_case: IntentTestCase
    classified_intent: str | None = None
    classified_route: str | None = None
    confidence: float | None = None
    reply_text: str | None = None
    check_results: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    elapsed_s: float = 0.0

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        return all(cr.passed for cr in self.check_results)

    @property
    def n_passed(self) -> int:
        return sum(1 for cr in self.check_results if cr.passed)

    @property
    def n_total(self) -> int:
        return len(self.check_results)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_unified(text: str, seq: int) -> UnifiedIncomingMessage:
    """Construct a minimal UnifiedIncomingMessage suitable for testing."""
    now = datetime.now(UTC)
    external_id = f"test_loop_tg_{seq}"
    return UnifiedIncomingMessage(
        event=EventPayload(
            event_id=f"telegram:test_{seq}",
            received_at=now,
            deduplication_key=f"telegram:test_{seq}",
            source_system="telegram",
        ),
        channel=ChannelPayload(code="telegram"),
        contact=ContactPayload(
            external_id=external_id,
            display_name="Test Loop User",
        ),
        conversation=ConversationPayload(external_chat_id=external_id),
        message=MessagePayload(
            external_message_id=f"msg_test_{seq}",
            sent_at=now,
            message_type="text",
            text=text,
            normalized_text=text,
        ),
        contact_match_keys=ContactMatchKeysPayload(),
        source_metadata=SourceMetadataPayload(provider="telegram"),
    )


# ── Test runner ───────────────────────────────────────────────────────────────

def run_test(tc: IntentTestCase, seq: int, rollback: bool = True) -> TestResult:
    """
    Run a single intent test case:
      1. Create a real DB session with commit patched to flush
      2. Mock send_telegram_message to capture the bot reply
      3. Call process_incoming_message with real Gemini + real DB reads
      4. Query the stored ConversationIntent for classification results
      5. Run all validators
      6. Roll back the session (unless --no-rollback)
    """
    result = TestResult(test_case=tc)
    session = SessionLocal()

    try:
        # Prevent any permanent writes: commit() just flushes within the transaction
        session.commit = session.flush  # type: ignore[method-assign]

        unified = _build_unified(tc.message, seq)
        captured: dict[str, str] = {}

        def _mock_send(chat_id: str, text: str) -> None:
            captured["chat_id"] = chat_id
            captured["text"] = text

        t0 = time.monotonic()

        with patch(
            "app.modules.inbound_messages.service.send_telegram_message",
            side_effect=_mock_send,
        ):
            process_incoming_message(session, unified)

        result.elapsed_s = time.monotonic() - t0
        result.reply_text = captured.get("text")

        # Retrieve the primary ConversationIntent that was just flushed
        intent_record = (
            session.query(ConversationIntent)
            .filter_by(is_primary=True)
            .order_by(ConversationIntent.id.desc())
            .first()
        )
        if intent_record:
            result.classified_intent = intent_record.intent_code
            result.classified_route = intent_record.route_type
            result.confidence = (
                float(intent_record.confidence) if intent_record.confidence is not None else None
            )

        result.check_results = run_checks(
            tc=tc,
            classified_intent=result.classified_intent,
            classified_route=result.classified_route,
            confidence=result.confidence,
            reply_text=result.reply_text,
            session=session,
        )

    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    finally:
        if rollback:
            try:
                session.rollback()
            except Exception:
                pass
        session.close()

    return result


# ── Output formatting ─────────────────────────────────────────────────────────

def _print_result(result: TestResult, idx: int, total: int, verbose: bool) -> None:
    tc = result.test_case
    intent_label = tc.intent_code.upper()
    msg_preview = tc.message[:52] + "…" if len(tc.message) > 52 else tc.message

    print(f"\n{_LINE}")
    print(f"{_BOLD}[{idx}/{total}] {intent_label}{_RESET}  {_DIM}{msg_preview}{_RESET}")
    print(_LINE)

    if result.error:
        print(f"  {_RED}ERROR  {result.error}{_RESET}")
        print(f"  {_RED}{_BOLD}RESULT: ERROR{_RESET}")
        return

    for cr in result.check_results:
        icon   = f"{_GREEN}✅{_RESET}" if cr.passed else f"{_RED}❌{_RESET}"
        detail = f"  {_DIM}{cr.detail}{_RESET}" if cr.detail else ""
        print(f"  {icon} {cr.name:<32}{detail}")

    if verbose and result.reply_text:
        print(f"\n  {_CYAN}Reply:{_RESET} {result.reply_text}")

    status_color = _GREEN if result.passed else _RED
    status_word  = "PASS" if result.passed else "FAIL"
    print(
        f"\n  {status_color}{_BOLD}RESULT: {status_word}{_RESET}"
        f"  ({result.n_passed}/{result.n_total} checks passed)"
        f"  {_DIM}{result.elapsed_s:.1f}s{_RESET}"
    )


def _print_summary(results: list[TestResult]) -> None:
    passed  = [r for r in results if r.passed]
    failed  = [r for r in results if not r.passed and not r.error]
    errored = [r for r in results if r.error]

    print(f"\n{_LINE}")
    print(f"{_BOLD}SUMMARY{_RESET}")
    print(_LINE)
    print(
        f"  {_GREEN}✅ Passed : {len(passed):<3}{_RESET}  "
        f"{_RED}❌ Failed : {len(failed):<3}{_RESET}  "
        f"{_YELLOW}⚠  Errors : {len(errored)}{_RESET}"
    )

    if failed:
        print(f"\n  {_RED}Failed intents:{_RESET}")
        for r in failed:
            bad_checks = [cr.name for cr in r.check_results if not cr.passed]
            print(f"    • {r.test_case.intent_code:<38}  {_DIM}{', '.join(bad_checks)}{_RESET}")

    if errored:
        print(f"\n  {_YELLOW}Errored intents:{_RESET}")
        for r in errored:
            print(f"    • {r.test_case.intent_code:<38}  {_DIM}{r.error}{_RESET}")

    total_elapsed = sum(r.elapsed_s for r in results)
    print(f"\n  Total time: {total_elapsed:.1f}s\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BrightSmile intent testing loop — real Gemini, real DB, mocked Telegram",
    )
    parser.add_argument(
        "--intent",
        metavar="CODE",
        help="Run only this intent code (e.g. greeting, price_question)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print the full bot reply for each test",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing test",
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Keep test rows in DB after each run (useful for debugging with psql)",
    )
    args = parser.parse_args()

    cases = INTENT_TEST_CASES
    if args.intent:
        cases = [tc for tc in cases if tc.intent_code == args.intent.lower()]
        if not cases:
            print(f"{_RED}No test case found for intent: '{args.intent}'{_RESET}")
            print(f"Available: {', '.join(tc.intent_code for tc in INTENT_TEST_CASES)}")
            sys.exit(1)

    total = len(cases)
    rollback = not args.no_rollback

    print(f"\n{_BOLD}BrightSmile — Intent Testing Loop{_RESET}")
    print(f"Running {total} test case(s)  ·  real Gemini  ·  real DB  ·  Telegram mocked")
    if not rollback:
        print(f"{_YELLOW}⚠  --no-rollback: test rows will persist in the database{_RESET}")

    results: list[TestResult] = []
    for idx, tc in enumerate(cases, 1):
        result = run_test(tc, seq=idx, rollback=rollback)
        results.append(result)
        _print_result(result, idx, total, verbose=args.verbose)

        if args.fail_fast and not result.passed:
            print(f"\n{_YELLOW}Stopping early (--fail-fast){_RESET}")
            break

    _print_summary(results)

    has_failures = any(not r.passed for r in results)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
