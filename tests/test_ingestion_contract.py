"""Carry actual synthetic ingestion provenance through retrieval and the API."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.writer_llm import _gather_citations
from lex_domus.contracts import citation_from_record
from lex_domus.ingestion import build_bundle, save_candidate
from tests.test_api import asgi_request
from tests.test_contracts import BOE_POLICY
from tests.test_ingestion import write_fixture


class IngestedContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lexdomus-ingested-contract-")
        self.addCleanup(temporary.cleanup)
        raw = ("\ufeff  \r\nDerechos patrimoniales morales y cláusula editorial sintética. 😀\r\n" * 35).encode("utf-8")
        self.fixture = write_fixture(temporary.name, raw)
        chunks, manifest = build_bundle(self.fixture["registry_path"], self.fixture["corpus"], BOE_POLICY)
        self.destination = save_candidate(Path(temporary.name) / "candidates", chunks, manifest)
        self.records = [json.loads(line) for line in chunks.splitlines()]
        for target, value in (
            ("lex_domus.rag_pipeline.POLICY_PATH", self.fixture["policy_path"]),
            ("lex_domus.retriever.CHUNKS", self.destination / "chunks.jsonl"),
            ("metrics_eee.logger.append_log", Mock()),
        ):
            self._patch(target, value)
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "llm.provider.call_llm_json"):
            guard = Mock(side_effect=AssertionError("Network and real providers forbidden"))
            self._patch(target, guard)
            self.addCleanup(guard.assert_not_called)
        environment = patch.dict("os.environ", {"USE_LLM": "0"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def _patch(self, target, value):
        patcher = patch(target, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ingested_coordinates_and_hashes_reach_http_and_writer(self):
        code, body = asyncio.run(asgi_request({"clause": "Cláusula editorial sintética.", "jurisdiction": "ES"}))
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "DRAFT_REVIEW_REQUIRED")
        by_id = {record["chunk_id"]: record for record in self.records}
        fields = ("doc_id", "chunk_id", "document_version", "source_sha256", "normalized_sha256",
                  "char_start", "char_end", "line_start", "line_end", "pinpoint", "ref_url")
        citations = [citation for item in body["per_node"] for citation in item["retrieval"]["citations"]]
        self.assertTrue(citations)
        for citation in citations:
            expected = by_id[citation["meta"]["chunk_id"]]
            for field in fields:
                self.assertEqual(citation["meta"][field], expected[field])
            self.assertEqual(citation["text"], expected["text"])
            self.assertFalse(citation["meta"]["pinpoint"])
        gathered = _gather_citations(body["per_node"])
        self.assertTrue(gathered)
        for citation in gathered:
            expected = by_id[citation["chunk_id"]]
            for field in ("doc_id", "chunk_id", "document_version", "source_sha256", "normalized_sha256", "char_start", "char_end"):
                self.assertEqual(citation[field], expected[field])

    def test_partial_or_impossible_provenance_cannot_be_retrieved(self):
        record = self.records[0]
        for change in ({"char_end": record["char_end"] + 1}, {"source_sha256": "bad-hash"},
                       {"document_version": " "}, {"char_start": True}, {"normalized_sha256": None}):
            with self.subTest(change=change):
                malformed = {**deepcopy(record), **change}
                self.assertIsNone(citation_from_record(malformed))
                (self.destination / "chunks.jsonl").write_text(json.dumps(malformed), encoding="utf-8")
                code, body = asyncio.run(asgi_request({"clause": "Cláusula editorial sintética.", "jurisdiction": "ES"}))
                self.assertEqual(code, 200)
                self.assertEqual(body["status"], "INSUFFICIENT_EVIDENCE")
                self.assertEqual(body["engine"], "NOT_RUN")

    def test_bom_and_whitespace_only_are_not_evidence(self):
        record = self.records[0]
        blank = "\ufeff \n\t"
        self.assertIsNone(citation_from_record({**record, "text": blank, "char_end": len(blank)}))
