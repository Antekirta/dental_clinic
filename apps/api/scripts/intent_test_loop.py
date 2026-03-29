#!/usr/bin/env python3
"""
Intent testing loop for BrightSmile chatbot.

Runs 10–20 messages per intent against the real Gemini API and local database,
then writes a self-contained HTML report table to scripts/intent_test_results.html.

Telegram sends are mocked — no real messages are dispatched.
Each test runs inside a DB transaction that is rolled back afterwards.

Usage:
    python scripts/intent_test_loop.py                    # all 28 intents
    python scripts/intent_test_loop.py --intent greeting  # one intent only
"""
from __future__ import annotations

import argparse
import html
import io
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

# Ensure stdout/stderr handle Unicode regardless of terminal encoding (e.g. cp1251).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, io.UnsupportedOperation):
        pass

# Allow sibling imports from the scripts directory.
sys.path.insert(0, str(Path(__file__).parent))

from intent_test_cases import INTENT_TEST_CASES, IntentTestCase  # noqa: E402

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

_REPORT_PATH = Path(__file__).parent / "intent_test_results.html"

# ── ANSI colours for terminal progress ───────────────────────────────────────
_GREEN = "\033[92m"
_RED   = "\033[91m"
_DIM   = "\033[2m"
_BOLD  = "\033[1m"
_RESET = "\033[0m"


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class RowResult:
    intent_code: str
    expected_intent: str
    expected_route: str
    question: str
    answer: str | None
    classified_intent: str | None
    classified_route: str | None
    confidence: float | None
    error: str | None = None

    @property
    def intent_match(self) -> bool:
        return self.classified_intent == self.expected_intent

    @property
    def route_match(self) -> bool:
        return self.classified_route == self.expected_route

    @property
    def fully_passed(self) -> bool:
        return (
            self.error is None
            and self.intent_match
            and self.route_match
            and bool(self.answer)  # reply must have been generated and sent
        )


# ── Test runner ───────────────────────────────────────────────────────────────

def _build_unified(text: str, seq: int) -> UnifiedIncomingMessage:
    now = datetime.now(UTC)
    eid = f"test_loop_{seq}"
    return UnifiedIncomingMessage(
        event=EventPayload(
            event_id=f"telegram:{eid}",
            received_at=now,
            deduplication_key=f"telegram:{eid}",
            source_system="telegram",
        ),
        channel=ChannelPayload(code="telegram"),
        contact=ContactPayload(external_id=eid, display_name="Test User"),
        conversation=ConversationPayload(external_chat_id=eid),
        message=MessagePayload(
            external_message_id=f"msg_{eid}",
            sent_at=now,
            message_type="text",
            text=text,
            normalized_text=text,
        ),
        contact_match_keys=ContactMatchKeysPayload(),
        source_metadata=SourceMetadataPayload(provider="telegram"),
    )


def run_single(
    tc: IntentTestCase,
    message: str,
    seq: int,
    rollback: bool = True,
) -> RowResult:
    row = RowResult(
        intent_code=tc.intent_code,
        expected_intent=tc.expected_intent,
        expected_route=tc.expected_route,
        question=message,
        answer=None,
        classified_intent=None,
        classified_route=None,
        confidence=None,
    )
    session = SessionLocal()
    try:
        session.commit = session.flush  # type: ignore[method-assign]
        unified = _build_unified(message, seq)
        captured: dict[str, str] = {}

        def _mock_send(chat_id: str, text: str) -> None:
            captured["text"] = text

        with patch(
            "app.modules.inbound_messages.service.send_telegram_message",
            side_effect=_mock_send,
        ):
            process_incoming_message(session, unified)

        row.answer = captured.get("text")

        intent_record = (
            session.query(ConversationIntent)
            .filter_by(is_primary=True)
            .order_by(ConversationIntent.id.desc())
            .first()
        )
        if intent_record:
            row.classified_intent = intent_record.intent_code
            row.classified_route = intent_record.route_type
            row.confidence = (
                float(intent_record.confidence)
                if intent_record.confidence is not None
                else None
            )
    except Exception as exc:
        row.error = f"{type(exc).__name__}: {exc}"
    finally:
        if rollback:
            try:
                session.rollback()
            except Exception:
                pass
        session.close()
    return row


# ── HTML report generator ─────────────────────────────────────────────────────

def _cell(value: bool, actual: str | None, expected: str) -> str:
    """Render an intent_match or route_match table cell."""
    if value:
        return '<td class="pass">✅</td>'
    label = html.escape(actual or "—")
    return f'<td class="fail">❌ <span class="got">got: {label}</span></td>'


def generate_html(rows: list[RowResult], elapsed_s: float) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total   = len(rows)
    passed  = sum(1 for r in rows if r.fully_passed)
    failed  = total - passed
    pct     = round(passed / total * 100) if total else 0

    # Group rows by intent for zebra striping
    intent_order: list[str] = []
    groups: dict[str, list[RowResult]] = {}
    for r in rows:
        if r.intent_code not in groups:
            intent_order.append(r.intent_code)
            groups[r.intent_code] = []
        groups[r.intent_code].append(r)

    tbody_parts: list[str] = []
    for i, intent_code in enumerate(intent_order):
        group_rows = groups[intent_code]
        stripe_class = "stripe-a" if i % 2 == 0 else "stripe-b"
        for row in group_rows:
            row_class = "row-pass" if row.fully_passed else "row-fail"
            if row.error:
                row_class = "row-error"

            q   = html.escape(row.question)
            ans = html.escape(row.answer) if row.answer else '<span class="no-answer">no reply generated</span>'
            conf = f"{row.confidence:.2f}" if row.confidence is not None else "—"

            im_cell  = _cell(row.intent_match,  row.classified_intent, row.expected_intent)
            rm_cell  = _cell(row.route_match,   row.classified_route,  row.expected_route)

            if row.error:
                im_cell = f'<td class="fail" colspan="2"><span class="got">{html.escape(row.error)}</span></td>'
                rm_cell = ""
                conf    = "—"

            tbody_parts.append(
                f'<tr class="{row_class} {stripe_class}">'
                f'<td class="intent-cell">{html.escape(intent_code)}</td>'
                f'<td class="q-cell">{q}</td>'
                f'<td class="a-cell">{ans}</td>'
                f"{im_cell}"
                f"{rm_cell}"
                f'<td class="conf-cell">{conf}</td>'
                f"</tr>"
            )

    tbody = "\n".join(tbody_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Intent Test Results — {ts}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; font-size: 14px; background: #f5f5f5; color: #222; }}
  header {{ background: #1a1a2e; color: #fff; padding: 20px 32px; }}
  header h1 {{ font-size: 20px; margin-bottom: 6px; }}
  .meta {{ font-size: 12px; color: #aaa; }}
  .stats {{ display: flex; gap: 24px; margin-top: 12px; }}
  .stat {{ background: #2a2a4e; padding: 8px 16px; border-radius: 6px; font-size: 13px; }}
  .stat .val {{ font-size: 22px; font-weight: bold; display: block; }}
  .stat.good .val {{ color: #4caf50; }}
  .stat.bad  .val {{ color: #f44336; }}
  .stat.neutral .val {{ color: #90caf9; }}
  .wrap {{ padding: 24px 32px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  thead th {{ background: #1a1a2e; color: #fff; padding: 10px 12px; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; position: sticky; top: 0; }}
  td {{ padding: 8px 12px; vertical-align: top; border-bottom: 1px solid #f0f0f0; }}
  .intent-cell {{ font-weight: 600; white-space: nowrap; font-size: 12px; color: #555; }}
  .q-cell  {{ max-width: 280px; }}
  .a-cell  {{ max-width: 360px; font-size: 13px; color: #444; }}
  .conf-cell {{ text-align: center; white-space: nowrap; font-size: 13px; }}
  .pass {{ text-align: center; color: #2e7d32; font-size: 15px; }}
  .fail {{ text-align: left; color: #c62828; font-size: 13px; }}
  .got  {{ font-size: 11px; color: #b71c1c; display: block; }}
  .empty {{ color: #bbb; }}
  .no-answer {{ color: #c62828; font-style: italic; font-size: 12px; }}
  .stripe-a.row-pass {{ background: #f9fff9; }}
  .stripe-b.row-pass {{ background: #f2fef2; }}
  .stripe-a.row-fail {{ background: #fff8f8; }}
  .stripe-b.row-fail {{ background: #fff0f0; }}
  .row-error {{ background: #fff3e0 !important; }}
  tr:hover td {{ filter: brightness(0.97); }}
</style>
</head>
<body>
<header>
  <h1>BrightSmile — Intent Test Results</h1>
  <div class="meta">Generated {ts} &nbsp;·&nbsp; {total} messages across {len(intent_order)} intents &nbsp;·&nbsp; completed in {elapsed_s:.0f}s</div>
  <div class="stats">
    <div class="stat good"><span class="val">{passed}</span>Passed</div>
    <div class="stat bad"><span class="val">{failed}</span>Failed</div>
    <div class="stat neutral"><span class="val">{pct}%</span>Pass rate</div>
  </div>
</header>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>Intent</th>
      <th>Question</th>
      <th>Answer</th>
      <th>intent_match</th>
      <th>route_match</th>
      <th>Confidence</th>
    </tr>
  </thead>
  <tbody>
{tbody}
  </tbody>
</table>
</div>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BrightSmile intent testing loop — generates an HTML report",
    )
    parser.add_argument(
        "--intent",
        metavar="CODE",
        help="Run only this intent code (e.g. greeting, price_question)",
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Keep test rows in DB after each run (for debugging)",
    )
    args = parser.parse_args()

    cases = INTENT_TEST_CASES
    if args.intent:
        cases = [tc for tc in cases if tc.intent_code == args.intent.lower()]
        if not cases:
            print(f"No test case found for intent: '{args.intent}'")
            print(f"Available: {', '.join(tc.intent_code for tc in INTENT_TEST_CASES)}")
            sys.exit(1)

    total_msgs = sum(len(tc.messages) for tc in cases)
    rollback = not args.no_rollback

    print(f"\n{_BOLD}BrightSmile — Intent Testing Loop{_RESET}")
    print(f"Running {total_msgs} messages across {len(cases)} intent(s)\n")

    all_rows: list[RowResult] = []
    seq = 0
    t_start = time.monotonic()

    for tc in cases:
        for i, message in enumerate(tc.messages, 1):
            seq += 1
            row = run_single(tc, message, seq, rollback=rollback)
            all_rows.append(row)

            icon = f"{_GREEN}✅{_RESET}" if row.fully_passed else f"{_RED}❌{_RESET}"
            conf = f"{row.confidence:.2f}" if row.confidence is not None else "  —"
            print(
                f"  {icon} [{tc.intent_code} {i}/{len(tc.messages)}]"
                f"  conf={conf}"
                f"  {_DIM}{message[:60]}{_RESET}"
            )

    elapsed = time.monotonic() - t_start

    # Summary
    passed = sum(1 for r in all_rows if r.fully_passed)
    failed = len(all_rows) - passed
    print(f"\n{'─' * 55}")
    print(f"  {_GREEN}✅ Passed: {passed}{_RESET}   {_RED}❌ Failed: {failed}{_RESET}   ({elapsed:.0f}s)")

    # Write HTML
    html_content = generate_html(all_rows, elapsed)
    _REPORT_PATH.write_text(html_content, encoding="utf-8")
    print(f"\n  Report saved → {_REPORT_PATH}\n")


if __name__ == "__main__":
    main()
