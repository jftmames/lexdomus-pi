"""Offline regressions for the professional-pilot HTTP boundary.

The ASGI application is called in process without an HTTP client dependency.
All clauses and citations are synthetic; providers and network connections are
guarded, including calls whose exceptions the application might otherwise hide.
These tests check the API contract, not the correctness of legal analysis.
"""

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from api.main import app
from app.pipeline import analyze_clause as real_analyze_clause
from tests.test_contracts import BOE_POLICY, synthetic_record


CLAUSE = "Cláusula editorial sintética para una prueba local."


def pipeline_result(has_evidence=True):
    """An internally consistent result with no real legal instrument or client."""
    citation = {
        "text": "Referencia sintética para comprobar la procedencia de una cita.",
        "meta": {
            "doc_id": "synthetic-document",
            "source": "BOE",
            "jurisdiction": "ES",
            "ref_url": "https://example.invalid/synthetic-document",
            "title": "Documento sintético",
            "ref_label": "Artículo sintético",
            "pinpoint": True,
            "line_start": 2,
            "line_end": 4,
        },
    }
    node = {
        "pregunta": "¿Qué derechos abarca esta cláusula sintética?",
        "encaje_ref": "Referencia sintética",
        "principio": "Criterio sintético",
        "evidencias_requeridas": ["Fuente sintética"],
        "alternativa": "Propuesta sintética sujeta a revisión",
    }
    return {
        "engine": "MOCK" if has_evidence else "NOT_RUN",
        "per_node": [{
            "node": node,
            "retrieval": {
                "status": "OK" if has_evidence else "NO_EVIDENCE",
                "citations": [citation] if has_evidence else [],
            },
            "used_query": node["pregunta"],
        }],
        "flags": [],
        "gate": {"status": "OK" if has_evidence else "NO_EVIDENCE"},
        "opinion": {
            "analysis_md": "Borrador sintético pendiente de revisión profesional.",
            "pros": [],
            "cons": [],
            "devils_advocate": {},
        } if has_evidence else None,
        "alternative_clause": "Alternativa sintética para pruebas." if has_evidence else None,
        "EEE": {"T": 1.0, "J": 1.0, "P": 1.0} if has_evidence else None,
    }


async def asgi_request(payload=None, *, raw_body=None, path="/analyze", method="POST", headers=(),
                       content_type=b"application/json"):
    """Collect an ordinary ASGI response, with no socket or lifespan startup."""
    body = raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", content_type),
                    (b"content-length", str(len(body)).encode("ascii")), *headers],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    messages = []
    delivered = False
    disconnected = asyncio.Event()

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        # Remain connected until the application completes its response. This
        # also works with Starlette's middleware that listens for disconnects.
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(message.get("body", b"") for message in messages
                             if message["type"] == "http.response.body")
    return start["status"], json.loads(response_body)


class AnalyzeApiTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"USE_LLM": "0"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            guard = Mock(side_effect=AssertionError("Network forbidden in API tests"))
            self._patch(target, guard)
            self.addCleanup(guard.assert_not_called)
        provider = Mock(side_effect=AssertionError("Real model provider forbidden in API tests"))
        self._patch("llm.provider.call_llm_json", provider)
        self.addCleanup(provider.assert_not_called)
        self.pipeline = self._patch("api.main.analyze_clause", Mock(return_value=pipeline_result()))

    def _patch(self, target, replacement):
        patcher = patch(target, replacement)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def request(self, payload=None, **kwargs):
        return asyncio.run(asgi_request(payload, **kwargs))

    def use_real_pipeline(self, *records):
        """Use the real analysis path, with only local corpus/policy/log fixtures."""
        from tests.snapshot_fixtures import create_snapshot_fixture, snapshot_environment
        temporary = tempfile.TemporaryDirectory(prefix="lexdomus-api-")
        self.addCleanup(temporary.cleanup)
        content = "\n".join(record["text"] for record in records) if records else "qzx987"
        fixture = create_snapshot_fixture(temporary.name, content.encode("utf-8"))
        self.ingested_record = json.loads(fixture["chunks_bytes"].splitlines()[0])
        environment = patch.dict(os.environ, snapshot_environment(fixture))
        environment.start()
        self.addCleanup(environment.stop)
        self._patch("lex_domus.snapshots.REGISTRY_PATH", fixture["registry_path"])
        self._patch("lex_domus.rag_pipeline.load_policy", Mock(return_value=BOE_POLICY))
        # Logging compatibility is a separate task; these HTTP regressions must
        # never append test clauses to the repository's persistent audit file.
        self._patch("metrics_eee.logger.append_log", Mock())
        self.pipeline.side_effect = real_analyze_clause

    def assert_envelope(self, body, expected_status):
        self.assertEqual(body["contract_version"], "0.2")
        self.assertEqual(body["status"], expected_status)
        self.assertEqual(str(UUID(body["request_id"])), body["request_id"])

    def assert_error(self, body, expected_status, *private_values):
        self.assert_envelope(body, expected_status)
        self.assertIsInstance(body["message"], str)
        self.assertTrue(body["message"])
        self.assertIsInstance(body["errors"], list)
        for error in body["errors"]:
            self.assertEqual(set(error), {"field", "code"})
            self.assertIn(error["field"], ("body", "clause", "jurisdiction"))
            self.assertIsInstance(error["code"], str)
            self.assertRegex(error["code"], r"^[A-Za-z][A-Za-z0-9_]*$")
        serialized = json.dumps(body, ensure_ascii=False)
        for private_value in private_values:
            self.assertNotIn(private_value, serialized)
        self.assertNotIn("traceback", serialized.lower())
        self.assertNotIn('"input"', serialized)
        self.assertNotIn('"ctx"', serialized)

    def test_valid_request_preserves_text_and_citation_provenance(self):
        clause = "  " + CLAUSE + "\n\t"
        code, body = self.request({"clause": clause, "jurisdiction": "ES"})
        self.assertEqual(code, 200)
        self.pipeline.assert_called_once_with(clause, "ES")
        self.assert_envelope(body, "DRAFT_REVIEW_REQUIRED")
        self.assertIs(body["review_required"], True)
        self.assertEqual(body["engine"], "MOCK")
        self.assertEqual(body["gate"]["status"], "OK")
        expected_node = pipeline_result()["per_node"][0]
        self.assertEqual(len(body["per_node"]), 1)
        actual_node = body["per_node"][0]
        self.assertEqual(actual_node["node"], expected_node["node"])
        self.assertEqual(actual_node["used_query"], expected_node["used_query"])
        actual_citation = actual_node["retrieval"]["citations"][0]
        expected_citation = expected_node["retrieval"]["citations"][0]
        self.assertEqual(actual_citation["text"], expected_citation["text"])
        for field, value in expected_citation["meta"].items():
            self.assertEqual(actual_citation["meta"][field], value)
        self.assertIsInstance(body["opinion"], dict)
        self.assertIsInstance(body["alternative_clause"], str)
        self.assertIsInstance(body["EEE"], dict)
        self.assertGreaterEqual(body["latency_ms"], 0)

    def test_one_character_and_exactly_5000_unicode_characters_are_accepted(self):
        for clause in ("x", "x" * 5000, "😀" * 5000, " " + "a" * 4998 + " "):
            with self.subTest(characters=len(clause), utf8_bytes=len(clause.encode("utf-8"))):
                self.pipeline.reset_mock()
                raw = json.dumps({"clause": clause, "jurisdiction": "ES"}, ensure_ascii=False).encode("utf-8")
                code, body = self.request(raw_body=raw)
                self.assertEqual(code, 200)
                self.assert_envelope(body, "DRAFT_REVIEW_REQUIRED")
                self.pipeline.assert_called_once_with(clause, "ES")

    def test_empty_or_whitespace_only_clauses_do_not_reach_pipeline(self):
        for clause in ("", " ", "\t\r\n", "\u00a0\u2003", "\ufeff", "\u0085", "\u001c", " \ufeff\n"):
            with self.subTest(clause=repr(clause)):
                code, body = self.request({"clause": clause, "jurisdiction": "ES"})
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT")
        self.pipeline.assert_not_called()

    def test_5001_characters_are_rejected_before_analysis(self):
        for clause in ("x" * 5001, "😀" * 5001, " " + "x" * 4999 + " "):
            with self.subTest(utf8_bytes=len(clause.encode("utf-8"))):
                code, body = self.request({"clause": clause, "jurisdiction": "ES"})
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", clause)
        self.pipeline.assert_not_called()

    def test_non_string_clauses_are_never_coerced(self):
        for clause in (None, 42, 1.5, True, ["PRIVATE_CLAUSE"], {"PRIVATE_KEY": "PRIVATE_VALUE"}):
            with self.subTest(clause=clause):
                code, body = self.request({"clause": clause, "jurisdiction": "ES"})
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", "PRIVATE_CLAUSE", "PRIVATE_KEY", "PRIVATE_VALUE")
        self.pipeline.assert_not_called()

    def test_missing_fields_and_non_object_bodies_are_rejected(self):
        for payload in ({}, {"clause": CLAUSE}, {"jurisdiction": "ES"}, None, [], "PRIVATE_BODY", 123):
            with self.subTest(payload=payload):
                code, body = self.request(payload)
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", CLAUSE, "PRIVATE_BODY")
        self.pipeline.assert_not_called()

    def test_unrecognized_fields_do_not_echo_the_field_name_or_value(self):
        code, body = self.request({
            "clause": CLAUSE,
            "jurisdiction": "ES",
            "private_case_identifier_739": "secret_client_name_739",
        })
        self.assertEqual(code, 422)
        self.assert_error(body, "INVALID_INPUT", CLAUSE, "private_case_identifier_739", "secret_client_name_739")
        self.pipeline.assert_not_called()

    def test_other_jurisdictions_are_out_of_scope_and_not_normalized(self):
        for jurisdiction in ("EU", "US", "INT", "es", "ES ", "", "PRIVATE_JURISDICTION"):
            with self.subTest(jurisdiction=jurisdiction):
                code, body = self.request({"clause": CLAUSE, "jurisdiction": jurisdiction})
                self.assertEqual(code, 422)
                self.assert_error(body, "OUT_OF_SCOPE", CLAUSE, "PRIVATE_JURISDICTION")
        self.pipeline.assert_not_called()

    def test_non_string_jurisdictions_are_invalid_input(self):
        for jurisdiction in (None, 1, False, ["ES"], {"private_jurisdiction": "ES"}):
            with self.subTest(jurisdiction=jurisdiction):
                code, body = self.request({"clause": CLAUSE, "jurisdiction": jurisdiction})
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", CLAUSE, "private_jurisdiction")
        self.pipeline.assert_not_called()

    def test_malformed_json_has_a_redacted_contract_error(self):
        for raw in (b'{"clause":"PRIVATE_UNCLOSED_CLAUSE', b'{"private_key":PRIVATE_INVALID_JSON}', b''):
            with self.subTest(raw=raw):
                code, body = self.request(raw_body=raw)
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", "PRIVATE_UNCLOSED_CLAUSE", "private_key", "PRIVATE_INVALID_JSON")
        self.pipeline.assert_not_called()

    def test_unpaired_surrogates_are_rejected_without_serialization_failure(self):
        for clause in ("private-surrogate-\ud800", "private-surrogate-\udfff", "\ud800x\udc00"):
            with self.subTest(clause=ascii(clause)):
                code, body = self.request({"clause": clause, "jurisdiction": "ES"})
                self.assertEqual(code, 422)
                self.assert_error(body, "INVALID_INPUT", "private-surrogate-")
        self.pipeline.assert_not_called()

    def test_non_json_content_type_cannot_bypass_json_validation(self):
        raw = json.dumps({"clause": "PRIVATE_TEXT_BODY", "jurisdiction": "ES"}).encode("utf-8")
        code, body = self.request(raw_body=raw, content_type=b"text/plain")
        self.assertEqual(code, 422)
        self.assert_error(body, "INVALID_INPUT", "PRIVATE_TEXT_BODY")
        self.pipeline.assert_not_called()

    def test_invalid_json_encoding_has_a_redacted_400_response(self):
        raw = b'{"clause":"PRIVATE_BAD_ENCODING_\xff","jurisdiction":"ES"}'
        code, body = self.request(raw_body=raw)
        self.assertEqual(code, 400)
        self.assert_error(body, "INVALID_INPUT", "PRIVATE_BAD_ENCODING_", "UnicodeDecodeError")
        self.pipeline.assert_not_called()

    def test_no_evidence_is_explicit_and_contains_no_generated_advice(self):
        self.pipeline.return_value = pipeline_result(has_evidence=False)
        code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
        self.assertEqual(code, 200)
        self.assert_envelope(body, "INSUFFICIENT_EVIDENCE")
        self.assertIs(body["review_required"], True)
        self.assertEqual(body["engine"], "NOT_RUN")
        self.assertEqual(body["gate"]["status"], "NO_EVIDENCE")
        self.assertIsNone(body["opinion"])
        self.assertIsNone(body["alternative_clause"])
        self.assertIsNone(body["EEE"])
        self.pipeline.assert_called_once_with(CLAUSE, "ES")

    def test_declared_llm_execution_is_still_a_draft_requiring_review(self):
        self.pipeline.return_value["engine"] = "LLM"
        code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
        self.assertEqual(code, 200)
        self.assert_envelope(body, "DRAFT_REVIEW_REQUIRED")
        self.assertIs(body["review_required"], True)
        self.assertEqual(body["engine"], "LLM")

    def test_real_pipeline_with_synthetic_corpus_produces_a_valid_draft_response(self):
        record = synthetic_record()
        self.use_real_pipeline(record)
        record = self.ingested_record
        code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
        self.assertEqual(code, 200)
        self.assert_envelope(body, "DRAFT_REVIEW_REQUIRED")
        self.assertIs(body["review_required"], True)
        self.assertEqual(body["engine"], "MOCK")
        self.assertEqual(body["gate"]["status"], "OK")
        self.assertTrue(body["opinion"]["analysis_md"].strip())
        citations = [citation for node in body["per_node"] for citation in node["retrieval"]["citations"]]
        self.assertTrue(citations)
        for citation in citations:
            for field in ("doc_id", "source", "jurisdiction", "ref_url", "line_start", "line_end"):
                self.assertEqual(citation["meta"][field], record[field])
        self.pipeline.assert_called_once_with(CLAUSE, "ES")

    def test_real_pipeline_with_valid_corpus_without_matches_abstains_before_generation(self):
        self.use_real_pipeline()
        generation_guards = []
        for target in ("app.writer_llm.draft_opinion_llm", "lex_domus.flagger.propose_alternative",
                       "metrics_eee.scorer.score_eee"):
            guard = Mock(side_effect=AssertionError("Generation forbidden without evidence"))
            self._patch(target, guard)
            generation_guards.append(guard)
        code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
        self.assertEqual(code, 200)
        self.assert_envelope(body, "INSUFFICIENT_EVIDENCE")
        self.assertIs(body["review_required"], True)
        self.assertEqual(body["engine"], "NOT_RUN")
        self.assertEqual(body["gate"]["status"], "NO_EVIDENCE")
        self.assertTrue(body["per_node"])
        self.assertTrue(all(not node["retrieval"]["citations"] for node in body["per_node"]))
        for field in ("opinion", "alternative_clause", "EEE"):
            self.assertIsNone(body[field])
        for guard in generation_guards:
            guard.assert_not_called()
        self.pipeline.assert_called_once_with(CLAUSE, "ES")

    def test_pipeline_failure_is_technical_error_without_exception_or_secret(self):
        self.pipeline.side_effect = RuntimeError("SECRET_API_KEY_739; PRIVATE_CASE_739; /private/corpus/path")
        with self.assertLogs("api.main", level="ERROR") as recorded:
            code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
        self.assertEqual(code, 500)
        self.assert_error(body, "TECHNICAL_ERROR", CLAUSE, "RuntimeError", "SECRET_API_KEY_739", "PRIVATE_CASE_739", "/private/corpus/path")
        log_output = "\n".join(recorded.output)
        self.assertIn(body["request_id"], log_output)
        for private_value in (CLAUSE, "SECRET_API_KEY_739", "PRIVATE_CASE_739", "/private/corpus/path"):
            self.assertNotIn(private_value, log_output)
        self.pipeline.assert_called_once_with(CLAUSE, "ES")

    def test_malformed_pipeline_results_are_not_returned_as_success(self):
        invalid_results = [None, [], {}, "PRIVATE_PIPELINE_RESULT"]
        for field, value in (("engine", "PRIVATE_ENGINE"), ("per_node", "PRIVATE_NODES"),
                             ("gate", {"status": "PRIVATE_GATE"}), ("opinion", "PRIVATE_OPINION"),
                             ("alternative_clause", 123), ("EEE", "PRIVATE_SCORE")):
            invalid = pipeline_result()
            invalid[field] = value
            invalid_results.append(invalid)
        missing_provenance = pipeline_result()
        del missing_provenance["per_node"][0]["retrieval"]["citations"][0]["meta"]["doc_id"]
        invalid_results.append(missing_provenance)
        for blank in ("", " \t\n", "\ufeff", "\u0085\u001c", " \ufeff\n"):
            invalid = pipeline_result()
            invalid["opinion"]["analysis_md"] = blank
            invalid_results.append(invalid)
        for index, invalid in enumerate(invalid_results):
            with self.subTest(case=index):
                self.pipeline.return_value = deepcopy(invalid)
                code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
                self.assertEqual(code, 500)
                self.assert_error(body, "TECHNICAL_ERROR", "PRIVATE_", CLAUSE)

    def test_conflicting_evidence_gate_and_generation_states_are_rejected(self):
        invalid_results = []
        no_citations = pipeline_result()
        no_citations["per_node"][0]["retrieval"]["citations"] = []
        invalid_results.append(no_citations)
        contradictory_gate = pipeline_result()
        contradictory_gate["gate"]["status"] = "NO_EVIDENCE"
        invalid_results.append(contradictory_gate)
        unexecuted_draft = pipeline_result()
        unexecuted_draft["engine"] = "NOT_RUN"
        invalid_results.append(unexecuted_draft)
        advice_without_evidence = pipeline_result(has_evidence=False)
        advice_without_evidence["alternative_clause"] = "PRIVATE_UNSUPPORTED_ADVICE"
        invalid_results.append(advice_without_evidence)
        for index, invalid in enumerate(invalid_results):
            with self.subTest(case=index):
                self.pipeline.return_value = invalid
                code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
                self.assertEqual(code, 500)
                self.assert_error(body, "TECHNICAL_ERROR", "PRIVATE_UNSUPPORTED_ADVICE", CLAUSE)

    def test_request_ids_are_fresh_even_if_a_client_supplies_one(self):
        supplied = "11111111-1111-4111-8111-111111111111"
        observed = []
        for expected_code, payload in ((200, {"clause": CLAUSE, "jurisdiction": "ES"}),
                                       (422, {"clause": "", "jurisdiction": "ES"})):
            code, body = self.request(payload, headers=[(b"x-request-id", supplied.encode("ascii"))])
            self.assertEqual(code, expected_code)
            observed.append(body["request_id"])
            self.assertEqual(str(UUID(body["request_id"])), body["request_id"])
            self.assertNotEqual(body["request_id"], supplied)
        self.assertNotEqual(observed[0], observed[1])

    def test_non_json_serializable_pipeline_values_have_a_redacted_500_response(self):
        invalid_results = []
        for value in (float("nan"), float("inf"), float("-inf")):
            result = pipeline_result()
            result["EEE"]["T"] = value
            invalid_results.append(result)
        surrogate = pipeline_result()
        surrogate["opinion"]["analysis_md"] = "PRIVATE_SERIALIZATION_FAILURE_\ud800"
        invalid_results.append(surrogate)
        for index, invalid in enumerate(invalid_results):
            with self.subTest(case=index):
                self.pipeline.return_value = invalid
                code, body = self.request({"clause": CLAUSE, "jurisdiction": "ES"})
                self.assertEqual(code, 500)
                self.assert_error(body, "TECHNICAL_ERROR", "PRIVATE_SERIALIZATION_FAILURE_", CLAUSE)


if __name__ == "__main__":
    unittest.main()
