"""Regressions for the Inquiry → RAG → writer contract.

All corpus records are synthetic. Component tests construct in-memory snapshots
and replace the file loader explicitly; snapshot verification is tested separately
in test_snapshots. These tests neither validate legal reasoning nor contact a
model provider or a legal-source website.
"""

import json
import os
import unittest
from unittest.mock import Mock, patch

from app.pipeline import analyze_clause
from app import writer_llm
from lex_domus import rag_pipeline, retriever, snapshots
from lex_domus.contracts import citation_from_record
from lex_domus.ingestion import canonical_json, digest
from lex_domus.snapshots import CorpusError, VerifiedSnapshot, tokenize
from verdiktia.inquiry_engine import decompose_clause
from lex_domus.policy import PolicyError


# Fictional approval for temporary synthetic records, never a deployable policy.
BOE_POLICY = {
    "schema_version": 1, "policy_id": "synthetic-only", "revision": 1,
    "jurisdiction": "ES", "reference_date": "2026-09-09",
    "review": {"status": "approved", "reviewer": "SYNTHETIC TEST REVIEWER",
               "reviewed_on": "2026-09-09", "record": "synthetic-test-only"},
    "sources": {"allowed": ["BOE"], "constraints": {
        "BOE": {"jurisdictions": ["ES"], "url_hosts": ["example.invalid"]}}},
}


def synthetic_record(doc_id="synthetic-lpi", source="BOE", text="derechos patrimoniales morales"):
    """A test fixture, not an extract from a legal instrument."""
    return {
        "text": text,
        "doc_id": doc_id,
        "source": source,
        "jurisdiction": "ES",
        "ref_url": "https://example.invalid/" + doc_id,
        "title": "Norma sintética para pruebas",
        "ref_label": "Artículo sintético",
        "pinpoint": True,
        "line_start": 2,
        "line_end": 4,
    }


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.loader = Mock(side_effect=self.fixture_snapshot)
        self._patch("lex_domus.snapshots.load_active_snapshot", self.loader)
        self._patch("lex_domus.retriever.load_active_snapshot", self.loader)
        self._patch_dict(os.environ, {"USE_LLM": "0"}, clear=True)
        self._patch("metrics_eee.logger.append_log", Mock())
        # Assert on calls as well as blocking them: a caught exception must not
        # conceal an accidental external request during these offline tests.
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            guard = Mock(side_effect=AssertionError("Network forbidden in contract tests"))
            self._patch(target, guard)
            self.addCleanup(guard.assert_not_called)
        provider = Mock(side_effect=AssertionError("Real provider forbidden in contract tests"))
        self._patch("llm.provider.call_llm_json", provider)
        self.addCleanup(provider.assert_not_called)

    def _patch(self, target, value):
        patcher = patch(target, value)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def _patch_dict(self, target, values, **kwargs):
        patcher = patch.dict(target, values, **kwargs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_records(self, *records):
        self.records = list(records)

    def fixture_snapshot(self, policy):
        """Unit fixture only: exercise search without claiming file verification."""
        citations = []
        for record in self.records:
            citation = citation_from_record(record)
            if citation is None:
                continue
            citation["meta"].update({
                "chunk_id": digest(canonical_json(record)),
                "document_version": "synthetic-v1",
                "source_sha256": "0" * 64,
                "normalized_sha256": digest(citation["text"].encode("utf-8")),
                "char_start": 0,
                "char_end": len(citation["text"]),
            })
            citations.append(citation)
        return VerifiedSnapshot(
            "1" * 64, "2" * 64, digest(canonical_json(policy)),
            tuple(json.dumps(citation) for citation in citations),
            tuple(tokenize(citation["text"]) for citation in citations),
        )

    def test_inquiry_produces_nonempty_canonical_questions(self):
        nodes = decompose_clause("Licencia editorial sintética.", "ES")
        self.assertTrue(nodes)
        for node in nodes:
            self.assertIsInstance(node["pregunta"], str)
            self.assertTrue(node["pregunta"].strip())

    def test_pipeline_queries_the_actual_inquiry_questions(self):
        self.write_records(synthetic_record())
        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch.object(
            rag_pipeline, "source_required_answer", wraps=rag_pipeline.source_required_answer
        ) as retrieve:
            result = analyze_clause("Licencia editorial sintética.", "ES")
        self.assertTrue(retrieve.call_args_list)
        queries = [call.args[0] for call in retrieve.call_args_list]
        for item in result["per_node"]:
            self.assertIn(item["node"]["pregunta"], queries)
            self.assertEqual(item["used_query"], item["node"]["pregunta"])
        self.assertTrue(all(isinstance(query, str) and query.strip() for query in queries))
        self.assertTrue(all("None" not in query for query in queries))
        self.loader.assert_called_once_with(BOE_POLICY)

    def test_pipeline_rejects_missing_or_empty_question_before_retrieval(self):
        for node in ({}, {"pregunta": ""}, {"pregunta": "   "}, {"pregunta": None}, {"question": "legacy"}):
            with self.subTest(node=node), patch(
                "verdiktia.inquiry_engine.decompose_clause", return_value=[node]
            ), patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch.object(
                rag_pipeline, "source_required_answer"
            ) as retrieve:
                with self.assertRaises(ValueError):
                    analyze_clause("Licencia editorial sintética.", "ES")
                retrieve.assert_not_called()

    def test_no_evidence_skips_writer_alternative_and_score_even_with_llm_enabled(self):
        with patch.dict(os.environ, {"USE_LLM": "1", "OPENAI_API_KEY": "synthetic-unused"}), patch.object(
            rag_pipeline, "load_policy", return_value=BOE_POLICY
        ), patch.object(writer_llm, "draft_opinion_llm") as writer, patch(
            "lex_domus.flagger.propose_alternative"
        ) as alternative, patch("metrics_eee.scorer.score_eee") as score:
            result = analyze_clause("Licencia editorial sintética.", "ES")
        self.assertEqual(result["gate"]["status"], "NO_EVIDENCE")
        self.assertEqual(result["engine"], "NOT_RUN")
        self.assertEqual(result["opinion"], {})
        self.assertEqual(result["alternative_clause"], "")
        self.assertIsNone(result["EEE"])
        writer.assert_not_called()
        alternative.assert_not_called()
        score.assert_not_called()

    def test_flat_corpus_identity_reaches_the_writer(self):
        record = synthetic_record()
        self.write_records(record)
        gathered = []
        original = writer_llm._gather_citations

        def capture_citations(*args, **kwargs):
            citations = original(*args, **kwargs)
            gathered.extend(citations)
            return citations

        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch.object(
            writer_llm, "_gather_citations", side_effect=capture_citations
        ):
            result = analyze_clause("Licencia editorial sintética.", "ES")
        self.assertTrue(gathered)
        for citation in gathered:
            self.assertEqual(citation["doc_id"], record["doc_id"])
            self.assertEqual(citation["source"], "BOE")
            self.assertEqual(citation["jurisdiction"], "ES")
            self.assertEqual(citation["url"], record["ref_url"])
            self.assertEqual(citation["lines"], [2, 4])
        self.assertEqual(result["engine"], "MOCK")

    def test_inquiry_error_does_not_invent_a_replacement_question(self):
        failure = RuntimeError("Synthetic inquiry failure")
        with patch("verdiktia.inquiry_engine.decompose_clause", side_effect=failure), patch.object(
            rag_pipeline, "load_policy", return_value=BOE_POLICY
        ), patch.object(rag_pipeline, "source_required_answer") as retrieve:
            with self.assertRaises(RuntimeError) as caught:
                analyze_clause("Licencia editorial sintética.", "ES")
            self.assertIs(caught.exception, failure)
            retrieve.assert_not_called()

    def test_flat_and_nested_records_preserve_identity_and_optional_metadata(self):
        flat = synthetic_record("flat")
        nested_flat = synthetic_record("nested")
        nested = {"text": nested_flat["text"], "meta": {key: value for key, value in nested_flat.items() if key != "text"}}
        citations = [citation_from_record(record) for record in (flat, nested)]
        self.assertEqual(len(citations), 2)
        by_id = {citation["meta"]["doc_id"]: citation for citation in citations}
        for expected in (flat, nested_flat):
            actual = by_id[expected["doc_id"]]
            self.assertEqual(actual["text"], expected["text"])
            for key, value in expected.items():
                if key != "text":
                    self.assertEqual(actual["meta"][key], value)

    def test_consistent_flat_and_nested_identity_is_accepted(self):
        record = synthetic_record()
        record["meta"] = {key: value for key, value in record.items() if key != "text"}
        citation = citation_from_record(record)
        self.assertIsNotNone(citation)
        self.assertEqual(citation["meta"]["doc_id"], "synthetic-lpi")

    def test_conflicting_flat_and_nested_identity_is_excluded(self):
        conflicts = {
            "doc_id": "other-document",
            "source": "UNKNOWN",
            "jurisdiction": "US",
            "ref_url": "https://example.invalid/other-document",
        }
        for key, value in conflicts.items():
            with self.subTest(field=key):
                record = synthetic_record()
                record["meta"] = {field: item for field, item in record.items() if field != "text"}
                record["meta"][key] = value
                self.assertIsNone(citation_from_record(record))

    def test_incomplete_identity_and_non_http_urls_are_excluded(self):
        for field in ("doc_id", "source", "jurisdiction", "ref_url"):
            with self.subTest(missing=field):
                record = synthetic_record()
                del record[field]
                self.assertIsNone(citation_from_record(record))
        for url in ("", "javascript:alert(1)", "file:///tmp/document", "https://", "not-a-url",
                    "https://exa mple.invalid/legal", "https://example.invalid:invalid/legal",
                    "https://example\n.invalid/legal", "https://@example.invalid/legal"):
            with self.subTest(url=url):
                record = synthetic_record()
                record["ref_url"] = url
                self.assertIsNone(citation_from_record(record))

    def test_corrupt_snapshot_aborts_before_inquiry_and_writer(self):
        failure = CorpusError("Synthetic corrupted evidence")
        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch.object(
            snapshots, "load_active_snapshot", side_effect=failure
        ), patch("verdiktia.inquiry_engine.decompose_clause") as inquiry, patch.object(
            retriever, "retrieve_candidates"
        ) as retrieve, patch.object(writer_llm, "draft_opinion_llm") as writer:
            with self.assertRaises(CorpusError) as caught:
                analyze_clause("Licencia editorial sintética.", "ES")
        self.assertIs(caught.exception, failure)
        inquiry.assert_not_called()
        retrieve.assert_not_called()
        writer.assert_not_called()

    def test_unauthorized_sources_cannot_displace_an_authorized_top_k_result(self):
        denied = [synthetic_record("denied-" + str(i), "UNKNOWN", "derechos morales licencia plazo") for i in range(6)]
        permitted = synthetic_record("permitted", "BOE", "derechos")
        self.write_records(*denied, permitted)
        result = rag_pipeline.source_required_answer("derechos morales licencia plazo", "ES", BOE_POLICY)
        self.assertEqual(result["status"], "OK")
        self.assertEqual([citation["meta"]["doc_id"] for citation in result["citations"]], ["permitted"])

    def test_unknown_or_missing_sources_are_never_admitted(self):
        missing_source = synthetic_record("missing-source")
        del missing_source["source"]
        self.write_records(synthetic_record("unknown", "UNKNOWN"), missing_source)
        result = rag_pipeline.source_required_answer("derechos", "ES", BOE_POLICY)
        self.assertEqual(result, {"status": "NO_EVIDENCE", "citations": []})

    def test_empty_or_malformed_explicit_policy_does_not_load_defaults(self):
        self.write_records(synthetic_record())
        policies = ({}, {"sources": {}}, {"sources": {"allowed": []}}, {"sources": {"allowed": "BOE"}}, {"sources": {"allowed": None}}, {"sources": []})
        for policy in policies:
            with self.subTest(policy=policy), patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY) as defaults:
                with self.assertRaises(PolicyError):
                    rag_pipeline.source_required_answer("derechos", "ES", policy)
                defaults.assert_not_called()

    def test_none_policy_uses_the_policy_loader(self):
        self.write_records(synthetic_record())
        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY) as defaults:
            result = rag_pipeline.source_required_answer("derechos", "ES", policy=None)
        defaults.assert_called_once_with()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["citations"][0]["meta"]["doc_id"], "synthetic-lpi")

    def test_empty_policy_remains_closed_through_the_pipeline(self):
        self.write_records(synthetic_record())
        with patch.object(rag_pipeline, "load_policy", return_value={}):
            with self.assertRaises(PolicyError):
                analyze_clause("Derechos morales y patrimoniales.", "ES")

    def test_retrieval_error_propagates_without_an_unfiltered_fallback(self):
        self.write_records(synthetic_record())
        failure = TypeError("Synthetic contract failure inside retrieval")
        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch.object(
            rag_pipeline, "source_required_answer", side_effect=failure
        ) as source_required, patch.object(retriever, "retrieve_candidates") as raw_retrieval:
            with self.assertRaises(TypeError) as caught:
                analyze_clause("Derechos morales y patrimoniales.", "ES")
            self.assertIs(caught.exception, failure)
            source_required.assert_called_once()
            raw_retrieval.assert_not_called()


if __name__ == "__main__":
    unittest.main()
