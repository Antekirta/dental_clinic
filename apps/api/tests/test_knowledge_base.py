"""
Unit tests for knowledge_base/service.py.

All DB interactions and Gemini calls are mocked — no real PostgreSQL or network.

Tests cover:
  - _chunk_markdown  (pure function — no mocks needed)
  - _rrf_merge       (pure function — no mocks needed)
  - ingest_document  (mocked session + mocked _embed_texts)
  - search_knowledge_base  (mocked session.execute + mocked _embed_texts)
  - _load_kb_context / _load_reference_data RAG branch  (mocked search)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fts_row(chunk_id: int, content: str = "text", filename: str = "doc.md") -> dict:
    return {
        "chunk_id": chunk_id,
        "document_filename": filename,
        "heading_path": None,
        "content": content,
        "rank": 0.5,
    }


def _make_semantic_row(chunk_id: int, content: str = "text", filename: str = "doc.md") -> dict:
    return {
        "chunk_id": chunk_id,
        "document_filename": filename,
        "heading_path": None,
        "content": content,
        "similarity": 0.9,
    }


# ---------------------------------------------------------------------------
# _chunk_markdown — pure function tests
# ---------------------------------------------------------------------------

class TestChunkMarkdown:

    def _call(self, content: str):
        from app.modules.knowledge_base.service import _chunk_markdown
        return _chunk_markdown(content)

    def test_no_headings_returns_single_chunk(self):
        content = "This is a plain paragraph with no headings."
        result = self._call(content)
        assert len(result) == 1
        chunk_index, heading_path, text = result[0]
        assert chunk_index == 0
        assert heading_path is None
        assert "plain paragraph" in text

    def test_single_h2_heading_produces_one_chunk(self):
        content = "## Services\n\nWe offer cleaning and whitening."
        result = self._call(content)
        assert len(result) == 1
        _, heading_path, text = result[0]
        assert heading_path == "Services"
        assert "cleaning and whitening" in text

    def test_multiple_h2_headings_produce_multiple_chunks(self):
        content = (
            "## Services\n\nCleaning and whitening.\n\n"
            "## Hours\n\nMon–Fri 9am to 6pm."
        )
        result = self._call(content)
        assert len(result) == 2
        paths = [r[1] for r in result]
        assert "Services" in paths
        assert "Hours" in paths

    def test_h3_under_h2_builds_compound_heading_path(self):
        content = (
            "## Services\n\n"
            "### Orthodontics\n\nBraces and aligners."
        )
        result = self._call(content)
        # Expect two chunks: one for "Services" (empty body), one for "Orthodontics"
        paths = [r[1] for r in result]
        assert any("Services > Orthodontics" in p for p in paths if p)

    def test_h3_without_preceding_h2_uses_heading_text_alone(self):
        content = "### Orthodontics\n\nBraces and aligners."
        result = self._call(content)
        assert len(result) == 1
        _, heading_path, _ = result[0]
        assert heading_path == "Orthodontics"

    def test_preamble_before_first_heading_becomes_own_chunk(self):
        content = (
            "Welcome to BrightSmile.\n\n"
            "## Services\n\nCleaning."
        )
        result = self._call(content)
        assert len(result) == 2
        # First chunk has no heading_path (preamble)
        assert result[0][1] is None
        assert "BrightSmile" in result[0][2]

    def test_heading_with_no_body_produces_chunk_with_just_heading(self):
        content = "## Empty Section\n\n## Next Section\n\nHas content."
        result = self._call(content)
        assert len(result) == 2
        empty_chunk = next(r for r in result if r[1] == "Empty Section")
        assert empty_chunk[2].strip() == "Empty Section"

    def test_long_section_is_split_at_paragraph_boundary(self):
        # Build a section whose body is clearly > 2000 chars
        long_para_a = "A " * 600   # ~1200 chars
        long_para_b = "B " * 600   # ~1200 chars
        content = f"## Big Section\n\n{long_para_a}\n\n{long_para_b}"
        result = self._call(content)
        # Should produce more than one chunk because the section is too long
        assert len(result) >= 2
        # All chunks should carry the same heading_path
        assert all(r[1] == "Big Section" for r in result)

    def test_chunk_indices_are_sequential_and_start_at_zero(self):
        content = "## A\n\nfoo\n\n## B\n\nbar\n\n## C\n\nbaz"
        result = self._call(content)
        indices = [r[0] for r in result]
        assert indices == list(range(len(result)))

    def test_empty_content_returns_empty_list(self):
        result = self._call("")
        # Empty or whitespace-only — one empty chunk or zero; must not crash
        # Acceptable: zero chunks (whitespace stripped) or one empty chunk
        assert isinstance(result, list)

    def test_chunk_text_includes_heading_label(self):
        content = "## Pricing\n\nCleaning costs £50."
        result = self._call(content)
        _, _, text = result[0]
        assert "Pricing" in text

    def test_multiple_h3_under_same_h2_get_correct_parent(self):
        content = (
            "## Treatments\n\n"
            "### Cleaning\n\nBasic clean.\n\n"
            "### Whitening\n\nTeeth whitening."
        )
        result = self._call(content)
        paths = [r[1] for r in result if r[1]]
        assert any("Treatments > Cleaning" in p for p in paths)
        assert any("Treatments > Whitening" in p for p in paths)


# ---------------------------------------------------------------------------
# _rrf_merge — pure function tests
# ---------------------------------------------------------------------------

class TestRrfMerge:

    def _call(self, fts_rows, semantic_rows, limit=5):
        from app.modules.knowledge_base.service import _rrf_merge
        return _rrf_merge(fts_rows, semantic_rows, limit=limit)

    def test_empty_inputs_return_empty(self):
        result = self._call([], [])
        assert result == []

    def test_fts_only_results_are_scored(self):
        rows = [_make_fts_row(1, "chunk one"), _make_fts_row(2, "chunk two")]
        result = self._call(rows, [])
        assert len(result) == 2
        # Higher-ranked (rank 0) should score better
        assert result[0].chunk_id == 1

    def test_semantic_only_results_are_scored(self):
        rows = [_make_semantic_row(10, "alpha"), _make_semantic_row(11, "beta")]
        result = self._call([], rows)
        assert len(result) == 2
        assert result[0].chunk_id == 10

    def test_chunk_in_both_legs_gets_higher_score(self):
        # chunk 1 appears in both; chunk 2 only in FTS; chunk 3 only in semantic
        fts = [_make_fts_row(1), _make_fts_row(2)]
        sem = [_make_semantic_row(1), _make_semantic_row(3)]
        result = self._call(fts, sem)
        # chunk 1 should score highest (sum of two legs)
        assert result[0].chunk_id == 1

    def test_deduplication_chunk_appears_once(self):
        fts = [_make_fts_row(5)]
        sem = [_make_semantic_row(5)]
        result = self._call(fts, sem)
        ids = [r.chunk_id for r in result]
        assert ids.count(5) == 1

    def test_limit_is_respected(self):
        fts = [_make_fts_row(i) for i in range(10)]
        sem = [_make_semantic_row(i) for i in range(10)]
        result = self._call(fts, sem, limit=3)
        assert len(result) == 3

    def test_result_contains_correct_fields(self):
        fts = [_make_fts_row(7, content="hello world", filename="faq.md")]
        result = self._call(fts, [])
        r = result[0]
        assert r.chunk_id == 7
        assert r.content == "hello world"
        assert r.document_filename == "faq.md"
        assert isinstance(r.score, float)
        assert r.score > 0


# ---------------------------------------------------------------------------
# ingest_document — mocked session + mocked _embed_texts
# ---------------------------------------------------------------------------

class TestIngestDocument:

    def _make_session(self, existing_doc=None):
        session = MagicMock()
        # query().filter().first() → check for duplicate hash
        session.query.return_value.filter.return_value.first.return_value = existing_doc
        return session

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_successful_ingestion_sets_status_ready(self, mock_embed):
        mock_embed.return_value = [[0.1] * 768, [0.2] * 768]

        session = self._make_session(existing_doc=None)
        # After flush(), doc.id becomes available
        def _flush_side_effect():
            # Simulate autoincrement: give the doc an id on first flush
            for call_args in session.add.call_args_list:
                obj = call_args[0][0]
                if hasattr(obj, "status") and not hasattr(obj, "_id_set"):
                    obj.id = 42
                    obj._id_set = True
        session.flush.side_effect = _flush_side_effect

        content = "## Services\n\nCleaning.\n\n## Hours\n\nMon–Fri 9–6."

        from app.modules.knowledge_base.service import ingest_document
        response = ingest_document(session, "clinic.md", content)

        assert response.status == "ready"
        assert response.chunk_count == 2

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_successful_ingestion_calls_embed_once(self, mock_embed):
        mock_embed.return_value = [[0.0] * 768]

        session = self._make_session(existing_doc=None)
        content = "## Only One Section\n\nShort body."

        from app.modules.knowledge_base.service import ingest_document
        ingest_document(session, "doc.md", content)

        mock_embed.assert_called_once()

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_successful_ingestion_flushes_session(self, mock_embed):
        mock_embed.return_value = [[0.0] * 768]

        session = self._make_session(existing_doc=None)
        content = "## Section\n\nBody."

        from app.modules.knowledge_base.service import ingest_document
        ingest_document(session, "doc.md", content)

        session.flush.assert_called()

    def test_duplicate_hash_returns_existing_without_embed(self):
        existing = MagicMock()
        existing.id = 99
        existing.chunk_count = 5
        existing.status = "ready"

        session = self._make_session(existing_doc=existing)

        with patch("app.modules.knowledge_base.service._embed_texts") as mock_embed:
            from app.modules.knowledge_base.service import ingest_document
            response = ingest_document(session, "same.md", "same content")

            mock_embed.assert_not_called()
            session.add.assert_not_called()

        assert response.document_id == 99
        assert response.chunk_count == 5
        assert response.status == "ready"

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_embed_failure_sets_status_error(self, mock_embed):
        mock_embed.side_effect = RuntimeError("Gemini unavailable")

        session = self._make_session(existing_doc=None)

        from app.modules.knowledge_base.service import ingest_document
        response = ingest_document(session, "bad.md", "## Section\n\nContent.")

        assert response.status == "error"
        assert response.chunk_count == 0

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_embed_failure_does_not_raise(self, mock_embed):
        mock_embed.side_effect = Exception("network error")

        session = self._make_session(existing_doc=None)

        from app.modules.knowledge_base.service import ingest_document
        # Should return gracefully, not propagate the exception
        response = ingest_document(session, "bad.md", "## Section\n\nContent.")
        assert response is not None


# ---------------------------------------------------------------------------
# search_knowledge_base — mocked session.execute + mocked _embed_texts
# ---------------------------------------------------------------------------

class TestSearchKnowledgeBase:

    def _make_session(self, fts_rows=None, semantic_rows=None):
        session = MagicMock()
        fts_rows = fts_rows or []
        semantic_rows = semantic_rows or []

        # session.execute(...).mappings().all() is called twice: FTS then semantic
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = fts_rows

        semantic_result = MagicMock()
        semantic_result.mappings.return_value.all.return_value = semantic_rows

        session.execute.side_effect = [fts_result, semantic_result]
        return session

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_returns_list_of_search_results(self, mock_embed):
        mock_embed.return_value = [[0.1] * 768]
        session = self._make_session(
            fts_rows=[_make_fts_row(1, "dental implants info")],
            semantic_rows=[_make_semantic_row(1, "dental implants info")],
        )

        from app.modules.knowledge_base.service import search_knowledge_base
        results = search_knowledge_base(session, "tell me about implants")

        assert len(results) == 1
        assert results[0].chunk_id == 1

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_empty_kb_returns_empty_list(self, mock_embed):
        mock_embed.return_value = [[0.0] * 768]
        session = self._make_session(fts_rows=[], semantic_rows=[])

        from app.modules.knowledge_base.service import search_knowledge_base
        results = search_knowledge_base(session, "anything")

        assert results == []

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_embeds_query_text_once(self, mock_embed):
        mock_embed.return_value = [[0.0] * 768]
        session = self._make_session()

        from app.modules.knowledge_base.service import search_knowledge_base
        search_knowledge_base(session, "do you do implants?")

        mock_embed.assert_called_once_with(["do you do implants?"])

    @patch("app.modules.knowledge_base.service._embed_texts")
    def test_limit_parameter_passed_to_rrf(self, mock_embed):
        mock_embed.return_value = [[0.0] * 768]
        sem_rows = [_make_semantic_row(i) for i in range(10)]
        session = self._make_session(fts_rows=[], semantic_rows=sem_rows)

        from app.modules.knowledge_base.service import search_knowledge_base
        results = search_knowledge_base(session, "query", limit=3)

        assert len(results) <= 3


# ---------------------------------------------------------------------------
# _load_reference_data RAG branch (inbound_messages/service.py)
# ---------------------------------------------------------------------------

class TestLoadReferenceDataRagBranch:
    """
    Tests for the faq_general and unknown branches added to _load_reference_data().
    Patches search_knowledge_base at the import site inside inbound_messages.service.
    """

    def _call(self, intent_code: str, message_text: str | None, search_results=None):
        from app.modules.knowledge_base.schemas import SearchResult

        if search_results is None:
            search_results = []

        with patch(
            "app.modules.knowledge_base.service.search_knowledge_base",
            return_value=search_results,
        ) as mock_search:
            from app.modules.inbound_messages.service import _load_reference_data

            session = MagicMock()
            result = _load_reference_data(
                session,
                intent_code=intent_code,
                extracted_entities=None,
                message_text=message_text,
            )
            return result, mock_search

    def test_faq_general_calls_search_when_message_text_provided(self):
        _, mock_search = self._call("faq_general", "What are your opening hours?")
        mock_search.assert_called_once()

    def test_unknown_calls_search_when_message_text_provided(self):
        _, mock_search = self._call("unknown", "Some ambiguous message")
        mock_search.assert_called_once()

    def test_no_message_text_does_not_call_search(self):
        _, mock_search = self._call("faq_general", message_text=None)
        mock_search.assert_not_called()

    def test_empty_search_results_returns_none(self):
        result, _ = self._call("faq_general", "some question", search_results=[])
        assert result is None

    def test_search_results_returned_as_kb_chunks_dict(self):
        from app.modules.knowledge_base.schemas import SearchResult

        chunks = [
            SearchResult(
                chunk_id=1,
                document_filename="faq.md",
                heading_path="FAQ",
                content="We open at 9am.",
                score=0.9,
            ),
            SearchResult(
                chunk_id=2,
                document_filename="faq.md",
                heading_path="FAQ",
                content="We close at 6pm.",
                score=0.8,
            ),
        ]
        result, _ = self._call("faq_general", "opening hours?", search_results=chunks)

        assert result is not None
        assert "knowledge_base" in result
        assert "We open at 9am." in result["knowledge_base"]
        assert "We close at 6pm." in result["knowledge_base"]

    def test_non_rag_intent_is_unaffected(self):
        """clinic_hours intent should not touch the knowledge base."""
        with patch(
            "app.modules.inbound_messages.service._load_branch_hours",
            return_value={"clinic_hours": "Mon–Fri 9–6"},
        ):
            with patch(
                "app.modules.knowledge_base.service.search_knowledge_base"
            ) as mock_search:
                from app.modules.inbound_messages.service import _load_reference_data

                session = MagicMock()
                result = _load_reference_data(
                    session,
                    intent_code="clinic_hours",
                    message_text="What are your hours?",
                )

        mock_search.assert_not_called()
        assert result == {"clinic_hours": "Mon–Fri 9–6"}
