"""Policy refusals must happen before reading evidence or generating advice."""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

from app.pipeline import analyze_clause
from lex_domus import rag_pipeline, retriever
from lex_domus.policy import PolicyError, read_policy, source_is_allowed, validate_policy
from tests.test_api import asgi_request
from tests.test_contracts import BOE_POLICY, synthetic_record


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lexdomus-policy-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "policy.yaml"
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "llm.provider.call_llm_json", "metrics_eee.logger.append_log"):
            guard = Mock(side_effect=AssertionError("External or persistent operation forbidden"))
            patcher = patch(target, guard)
            patcher.start()
            self.addCleanup(patcher.stop)
            self.addCleanup(guard.assert_not_called)

    def test_missing_empty_corrupt_and_duplicate_yaml_never_load_defaults(self):
        with self.assertRaises(PolicyError):
            read_policy(self.path)
        for content in ("", "[", "null", "[]", "sources: {}", "sources: {}\nsources: {}",
                        "? [bad, key]\n: value", "a: &a\n  b: *a", "x: !unknown foo"):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                with self.assertRaises(PolicyError):
                    read_policy(self.path)
        self.path.write_bytes(b"\xff")
        with self.assertRaises(PolicyError):
            read_policy(self.path)

    def test_valid_quoted_policy_roundtrips_without_defaults(self):
        self.path.write_text(yaml.safe_dump(BOE_POLICY), encoding="utf-8")
        self.assertEqual(read_policy(self.path), BOE_POLICY)

    def test_pending_policy_cannot_run_even_in_mock_mode(self):
        pending = yaml.safe_load(rag_pipeline.POLICY_PATH.read_text(encoding="utf-8"))
        validate_policy(pending, require_approved=False)
        with patch("verdiktia.inquiry_engine.decompose_clause") as inquiry, patch(
            "lex_domus.retriever.retrieve_candidates"
        ) as retrieval, patch("app.writer_llm.draft_opinion_llm") as writer:
            with self.assertRaises(PolicyError):
                analyze_clause("Cláusula sintética", "ES")
        inquiry.assert_not_called()
        retrieval.assert_not_called()
        writer.assert_not_called()

    def test_public_api_returns_controlled_503_without_content_or_paths(self):
        clause = "CONTENIDO PRIVADO SINTETICO"
        code, body = asyncio.run(asgi_request({"clause": clause, "jurisdiction": "ES"}))
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "TECHNICAL_ERROR")
        self.assertNotIn(clause, str(body))
        self.assertNotIn(str(rag_pipeline.POLICY_PATH), str(body))
        self.assertNotIn("opinion", body)
        self.assertIn("request_id", body)

    def test_direct_retrieval_also_requires_an_approved_policy(self):
        with patch.object(retriever, "CHUNKS", self.path):
            for policy in (None, {}, {"sources": {"allowed": ["BOE"]}}):
                with self.subTest(policy=policy), self.assertRaises(PolicyError):
                    retriever.retrieve_candidates("derechos", policy=policy)

    def test_explicit_invalid_policy_is_rejected_before_retrieval(self):
        variants = []
        for key, value in (("schema_version", True), ("revision", 0), ("revision", True),
                           ("jurisdiction", "US"), ("reference_date", "2099-01-01"),
                           ("reference_date", "2026-02-30"), ("policy_id", " ")):
            candidate = deepcopy(BOE_POLICY)
            candidate[key] = value
            variants.append(candidate)
        for key, value in (("reviewer", ""), ("record", None), ("reviewed_on", "2099-01-01"),
                           ("reviewed_on", "2020-01-01"),
                           ("status", "unknown")):
            candidate = deepcopy(BOE_POLICY)
            candidate["review"][key] = value
            variants.append(candidate)
        for candidate in variants:
            with self.subTest(candidate=candidate), patch.object(retriever, "retrieve_candidates") as retrieve:
                with self.assertRaises(PolicyError):
                    rag_pipeline.source_required_answer("derechos", "ES", candidate)
                retrieve.assert_not_called()

    def test_unknown_source_scope_and_deceptive_host_are_excluded(self):
        meta = synthetic_record()
        self.assertTrue(source_is_allowed(BOE_POLICY, meta))
        for field, value in (("source", "UNKNOWN"), ("source", ["BOE"]), ("jurisdiction", "US"),
                             ("ref_url", "https://example.invalid.evil.test/x"),
                             ("ref_url", "https://evil.test/example.invalid/x"),
                             ("ref_url", "https://user@example.invalid/x"),
                             ("ref_url", "https://example.invalid:444/x"),
                             ("ref_url", "http://example.invalid/x")):
            with self.subTest(field=field, value=value):
                self.assertFalse(source_is_allowed(BOE_POLICY, {**meta, field: value}))

    def test_old_reference_year_is_not_an_expiry_heuristic(self):
        old = deepcopy(BOE_POLICY)
        old["reference_date"] = "1996-04-22"
        validate_policy(old)
        self.assertTrue(source_is_allowed(old, synthetic_record()))

    def test_non_es_direct_pipeline_calls_cannot_bypass_scope(self):
        with patch.object(rag_pipeline, "load_policy", return_value=BOE_POLICY), patch(
            "verdiktia.inquiry_engine.decompose_clause"
        ) as inquiry:
            for jurisdiction in ("US", "EU", "INT"):
                with self.subTest(jurisdiction=jurisdiction), self.assertRaises(PolicyError):
                    analyze_clause("Cláusula sintética", jurisdiction)
            inquiry.assert_not_called()
