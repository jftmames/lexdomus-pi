"""Offline ingestion regressions using explicitly fictional, temporary sources.

Recorded reviewers, reuse bases and URLs below are synthetic test data. They
must never be used as approval or provenance for an actual legal instrument.
"""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lex_domus.ingestion import (
    IngestionError, build_bundle, canonical_json, inspect_registry, save_candidate,
)
from lex_domus.policy import PolicyError
from scripts import ingest
from tests.test_contracts import BOE_POLICY


def synthetic_provenance(doc_id="synthetic-editorial", version="synthetic-v1"):
    """Complete fictional provenance; no professional approval is implied."""
    return {
        "doc_id": doc_id, "source": "BOE", "jurisdiction": "ES",
        "title": "Documento enteramente sintético para pruebas",
        "family": "synthetic-only", "ref_url": "https://example.invalid/" + doc_id,
        "version": version, "version_date": "2026-09-09", "language": "es",
        "retrieved_on": "2026-09-09", "content_kind": "normative_text",
        "review": {"reviewer": "SYNTHETIC TEST REVIEWER", "reviewed_on": "2026-09-09",
                   "record": "synthetic-review-only"},
        "reuse": {"basis": "Original synthetic test fixture", "record": "synthetic-reuse-only"},
    }


def write_fixture(root, content=b"Texto sintetico sobre licencia editorial.\n"):
    """Write a self-contained fixture and return its paths plus mutable registry."""
    root = Path(root)
    corpus = root / "data/corpus"
    policies = root / "policies"
    corpus.mkdir(parents=True)
    policies.mkdir(parents=True)
    source = corpus / "source.txt"
    source.write_bytes(content)
    registry = {
        "schema_version": 1, "registry_id": "synthetic-registry-only", "revision": 1,
        "documents": [{"path": source.name, "sha256": hashlib.sha256(content).hexdigest(),
                       "state": "admitted", "reason": "Synthetic fixture only",
                       "provenance": synthetic_provenance()}],
    }
    registry_path = policies / "corpus-registry.json"
    registry_path.write_bytes(canonical_json(registry))
    policy_path = policies / "policy.yaml"
    policy_path.write_text(json.dumps(BOE_POLICY), encoding="utf-8")
    return {"root": root, "corpus": corpus, "source": source, "registry": registry,
            "registry_path": registry_path, "policy_path": policy_path}


class IngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lexdomus-ingestion-")
        self.addCleanup(temporary.cleanup)
        self.fixture = write_fixture(temporary.name)
        self.root = self.fixture["root"]
        self.corpus = self.fixture["corpus"]
        self.registry = self.fixture["registry"]
        self.registry_path = self.fixture["registry_path"]
        self.policy = deepcopy(BOE_POLICY)
        environment = patch.dict(os.environ, {"USE_LLM": "0"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "llm.provider.call_llm_json"):
            guard = Mock(side_effect=AssertionError("External requests forbidden in ingestion tests"))
            patcher = patch(target, guard)
            patcher.start()
            self.addCleanup(patcher.stop)
            self.addCleanup(guard.assert_not_called)

    def write_registry(self):
        self.registry_path.write_bytes(canonical_json(self.registry))

    def set_source(self, content):
        self.fixture["source"].write_bytes(content)
        self.registry["documents"][0]["sha256"] = hashlib.sha256(content).hexdigest()
        self.write_registry()

    def add_copy(self, name, *, content=None, provenance=None):
        if content is None:
            content = self.fixture["source"].read_bytes()
        entry = deepcopy(self.registry["documents"][0])
        entry.update(path=name, sha256=hashlib.sha256(content).hexdigest())
        if provenance is not None:
            entry["provenance"] = provenance
        (self.corpus / name).write_bytes(content)
        self.registry["documents"].append(entry)
        self.write_registry()

    def build(self, **kwargs):
        return build_bundle(self.registry_path, self.corpus, self.policy, **kwargs)

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(ingest, "ROOT", self.root), redirect_stdout(stdout), redirect_stderr(stderr):
            status = ingest.main(list(args))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_complete_coverage_preserves_unicode_long_lines_and_whitespace(self):
        raw = "\ufeff  Título: niña, §, e\u0301, 😀\r\n\r\n" + "界ñ😀 " * 650 + "\rFin\r\n" + " \t\r\n" * 35
        self.set_source(raw.encode("utf-8"))
        chunks, encoded_manifest = self.build(max_chars=53, overlap_chars=11)
        records = [json.loads(line) for line in chunks.splitlines()]
        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        reconstructed, covered = "", 0
        for record in records:
            start, end = record["char_start"], record["char_end"]
            self.assertEqual(record["text"], normalized[start:end])
            self.assertLessEqual(end - start, 53)
            self.assertLessEqual(start, covered)
            self.assertGreater(end, covered)
            self.assertEqual(record["line_start"], normalized[:start].count("\n") + 1)
            self.assertEqual(record["line_end"], normalized[:end - 1].count("\n") + 1)
            reconstructed += record["text"][covered - start:]
            covered = end
        self.assertEqual(reconstructed, normalized)
        self.assertTrue(any(not record["text"].strip() for record in records))
        manifest = json.loads(encoded_manifest)
        self.assertEqual(manifest["documents"][0]["covered_characters"], len(normalized))
        self.assertEqual(manifest["documents"][0]["normalized_characters"], len(normalized))

    def test_manifest_and_chunk_hashes_bind_inputs_and_coordinates(self):
        self.set_source("  Cláusula sintética\r\ncon versión.\r".encode("utf-8"))
        chunks, encoded_manifest = self.build(max_chars=17, overlap_chars=3)
        manifest = json.loads(encoded_manifest)
        records = [json.loads(line) for line in chunks.splitlines()]
        self.assertEqual(manifest["chunks_sha256"], hashlib.sha256(chunks).hexdigest())
        self.assertEqual(manifest["registry_sha256"], hashlib.sha256(self.registry_path.read_bytes()).hexdigest())
        self.assertEqual(manifest["policy_sha256"], hashlib.sha256(canonical_json(self.policy)).hexdigest())
        self.assertEqual(manifest["chunk_count"], len(records))
        corpus_id = manifest.pop("corpus_id")
        self.assertEqual(corpus_id, hashlib.sha256(canonical_json(manifest)).hexdigest())
        document = manifest["documents"][0]
        source_hash = hashlib.sha256(self.fixture["source"].read_bytes()).hexdigest()
        normalized_hash = hashlib.sha256("  Cláusula sintética\ncon versión.\n".encode("utf-8")).hexdigest()
        self.assertEqual(document["source_sha256"], source_hash)
        self.assertEqual(document["normalized_sha256"], normalized_hash)
        self.assertEqual(document["chunk_count"], len(records))
        self.assertEqual(document["provenance"], synthetic_provenance())
        self.assertEqual(len({record["chunk_id"] for record in records}), len(records))
        for record in records:
            expected = {"doc_id": "synthetic-editorial", "version": "synthetic-v1",
                        "source_sha256": source_hash, "start": record["char_start"], "end": record["char_end"]}
            self.assertEqual(record["chunk_id"], hashlib.sha256(canonical_json(expected)).hexdigest())
            self.assertEqual(record["source_sha256"], source_hash)
            self.assertEqual(record["normalized_sha256"], normalized_hash)
            self.assertEqual(record["document_version"], "synthetic-v1")
            self.assertFalse(record["pinpoint"])

    def test_two_builds_are_byte_identical(self):
        self.add_copy("another.txt", provenance=synthetic_provenance("synthetic-other"))
        self.assertEqual(self.build(), self.build())

    def test_identical_document_copies_collapse_to_canonical_path_with_alias(self):
        self.add_copy("a-canonical.txt")
        chunks, encoded_manifest = self.build()
        manifest = json.loads(encoded_manifest)
        self.assertEqual(len(manifest["documents"]), 1)
        self.assertEqual(manifest["documents"][0]["path"], "a-canonical.txt")
        self.assertEqual(manifest["duplicates"], [{
            "path": "source.txt", "canonical_path": "a-canonical.txt",
            "doc_id": "synthetic-editorial", "version": "synthetic-v1",
            "sha256": self.registry["documents"][0]["sha256"],
        }])
        self.assertEqual(len(chunks.splitlines()), manifest["documents"][0]["chunk_count"])

    def test_same_identity_with_different_content_is_rejected(self):
        self.add_copy("other.txt", content=b"Different synthetic source content.\n")
        with self.assertRaisesRegex(IngestionError, "Conflicting"):
            self.build()

    def test_same_identity_with_different_review_is_rejected(self):
        provenance = synthetic_provenance()
        provenance["review"]["record"] = "different-synthetic-review"
        self.add_copy("other.txt", provenance=provenance)
        with self.assertRaisesRegex(IngestionError, "Conflicting"):
            self.build()

    def test_same_bytes_for_different_documents_or_versions_are_preserved(self):
        self.add_copy("different-id.txt", provenance=synthetic_provenance("synthetic-other"))
        self.add_copy("different-version.txt", provenance=synthetic_provenance(version="synthetic-v2"))
        chunks, encoded_manifest = self.build()
        manifest = json.loads(encoded_manifest)
        self.assertEqual(len(manifest["documents"]), 3)
        self.assertEqual(manifest["duplicates"], [])
        self.assertEqual(len({json.loads(line)["chunk_id"] for line in chunks.splitlines()}), 3)

    def test_registry_missing_and_duplicate_keys_are_rejected(self):
        self.registry_path.unlink()
        with self.assertRaises(IngestionError):
            self.build()
        for malformed in (b'{"schema_version":1,"schema_version":1}',
                          canonical_json(self.registry).replace(b'"reviewer":', b'"reviewer":"duplicate","reviewer":')):
            with self.subTest(registry=malformed):
                self.registry_path.write_bytes(malformed)
                with self.assertRaises(IngestionError):
                    self.build()

    def test_source_path_cannot_escape_registry_or_be_duplicated(self):
        original = deepcopy(self.registry)
        for name in ("../source.txt", "/source.txt", "sub/source.txt", "..\\source.txt", " source.txt", "file.TXT"):
            with self.subTest(path=name):
                self.registry = deepcopy(original)
                self.registry["documents"][0]["path"] = name
                self.write_registry()
                with self.assertRaises(IngestionError):
                    self.build()
        self.registry = deepcopy(original)
        self.registry["documents"].append(deepcopy(original["documents"][0]))
        self.write_registry()
        with self.assertRaises(IngestionError):
            self.build()

    def test_admitted_symlink_missing_file_and_hash_mismatch_are_rejected(self):
        source = self.fixture["source"]
        original = source.read_bytes()
        source.unlink()
        with self.assertRaisesRegex(IngestionError, "integrity"):
            self.build()
        target = self.root / "outside.txt"
        target.write_bytes(original)
        source.symlink_to(target)
        with self.assertRaisesRegex(IngestionError, "integrity"):
            self.build()
        source.unlink()
        source.write_bytes(original + b"changed")
        with self.assertRaisesRegex(IngestionError, "integrity"):
            self.build()

    def test_blank_and_invalid_utf8_sources_are_rejected_even_with_matching_hash(self):
        for content in (b"", b" \r\n\t\n", "\ufeff \n\t".encode("utf-8"), b"invalid UTF-8: \xff"):
            with self.subTest(content=content):
                self.set_source(content)
                with self.assertRaises(IngestionError):
                    self.build()

    def test_incomplete_provenance_or_reuse_review_is_rejected(self):
        original = synthetic_provenance()
        variants = []
        for key in ("doc_id", "version", "retrieved_on", "review", "reuse"):
            value = deepcopy(original)
            del value[key]
            variants.append(value)
        for key in ("review", "reuse"):
            value = deepcopy(original)
            value[key]["record"] = "   "
            variants.append(value)
        value = deepcopy(original)
        value["content_kind"] = "placeholder"
        variants.append(value)
        value = deepcopy(original)
        value["review"]["reviewed_on"] = "2026-09-08"
        variants.append(value)
        for provenance in variants:
            with self.subTest(provenance=provenance):
                self.registry["documents"][0]["provenance"] = provenance
                self.write_registry()
                with self.assertRaises(IngestionError):
                    self.build()

    def test_unregistered_file_stays_in_quarantine_and_never_enters_chunks(self):
        (self.corpus / "unknown.txt").write_bytes(b"UNREVIEWED SENTINEL \xff")
        chunks, encoded_manifest = self.build()
        manifest = json.loads(encoded_manifest)
        self.assertEqual(manifest["quarantined"], [{
            "path": "unknown.txt", "reason": "unregistered_source", "expected_sha256": None,
            "actual_sha256": None, "integrity_issue": None,
        }])
        self.assertNotIn(b"UNREVIEWED", chunks)

    def test_registered_quarantine_reports_integrity_without_admitting_content(self):
        self.add_copy("quarantine.txt", content=b"QUARANTINED SENTINEL")
        entry = self.registry["documents"][1]
        entry.update(state="quarantined", reason="Synthetic quarantine", provenance=None, sha256="0" * 64)
        self.write_registry()
        chunks, encoded_manifest = self.build()
        manifest = json.loads(encoded_manifest)
        self.assertEqual(len(manifest["documents"]), 1)
        self.assertEqual(manifest["quarantined"][0]["integrity_issue"], "hash_mismatch")
        self.assertNotIn(b"QUARANTINED", chunks)

    def test_admitted_source_outside_policy_is_rejected(self):
        for field, value in (("source", "UNKNOWN"), ("jurisdiction", "US"),
                             ("ref_url", "https://unapproved.invalid/source")):
            with self.subTest(field=field):
                provenance = synthetic_provenance()
                provenance[field] = value
                self.registry["documents"][0]["provenance"] = provenance
                self.write_registry()
                with self.assertRaisesRegex(IngestionError, "outside policy"):
                    self.build()

    def test_no_admitted_sources_cannot_make_an_empty_candidate(self):
        self.registry["documents"][0].update(state="quarantined", provenance=None)
        self.write_registry()
        with self.assertRaisesRegex(IngestionError, "No reviewed"):
            self.build()

    def test_candidate_saving_never_overwrites_existing_siblings(self):
        chunks, manifest = self.build()
        parent = self.root / "candidates"
        parent.mkdir()
        (parent / "chunks.jsonl").write_bytes(b"EXISTING ACTIVE SENTINEL")
        first = save_candidate(parent, chunks, manifest)
        second = save_candidate(parent, chunks, manifest)
        self.assertNotEqual(first, second)
        self.assertEqual((parent / "chunks.jsonl").read_bytes(), b"EXISTING ACTIVE SENTINEL")
        for destination in (first, second):
            self.assertEqual(destination.parent, parent)
            self.assertEqual((destination / "chunks.jsonl").read_bytes(), chunks)
            self.assertEqual((destination / "manifest.json").read_bytes(), manifest)

    def test_candidate_write_failure_cleans_only_its_partial_directory(self):
        parent = self.root / "candidates"
        parent.mkdir()
        sibling = parent / "previous-candidate"
        sibling.mkdir()
        (sibling / "manifest.json").write_bytes(b"UNCHANGED PREVIOUS CANDIDATE")
        real_write = Path.write_bytes

        def fail_manifest(path, content):
            if path.name == "manifest.json":
                raise OSError("Synthetic disk failure")
            return real_write(path, content)

        with patch.object(Path, "write_bytes", fail_manifest), self.assertRaisesRegex(IngestionError, "finish"):
            save_candidate(parent, b"chunks", b"manifest")
        self.assertEqual(list(parent.iterdir()), [sibling])
        self.assertEqual((sibling / "manifest.json").read_bytes(), b"UNCHANGED PREVIOUS CANDIDATE")

    def test_cli_builds_explicit_candidate_and_leaves_active_artifacts_unchanged(self):
        active = self.root / "data/docs_chunks/chunks.jsonl"
        active.parent.mkdir(parents=True)
        active.write_bytes(b"ACTIVE CHUNKS SENTINEL")
        index = self.root / "indices/bm25.pkl"
        index.parent.mkdir()
        index.write_bytes(b"ACTIVE INDEX SENTINEL")
        output = self.root / "candidates"
        status, stdout, stderr = self.cli("--output-dir", str(output))
        self.assertEqual((status, stderr), (0, ""))
        self.assertIn("candidate ->", stdout)
        candidates = list(output.glob("candidate-*"))
        self.assertEqual(len(candidates), 1)
        expected_chunks, expected_manifest = self.build()
        self.assertEqual((candidates[0] / "chunks.jsonl").read_bytes(), expected_chunks)
        self.assertEqual((candidates[0] / "manifest.json").read_bytes(), expected_manifest)
        self.assertEqual(active.read_bytes(), b"ACTIVE CHUNKS SENTINEL")
        self.assertEqual(index.read_bytes(), b"ACTIVE INDEX SENTINEL")

    def test_cli_without_explicit_output_is_blocked_even_for_approved_fixture(self):
        status, _, _ = self.cli()
        self.assertEqual(status, 2)
        self.assertFalse((self.root / "data/corpus_candidates").exists())
        self.assertFalse(list(self.root.rglob("candidate-*")))

    def test_pending_default_policy_blocks_build_without_output_files(self):
        pending = deepcopy(self.policy)
        pending["review"] = {"status": "pending", "reviewer": None, "reviewed_on": None, "record": None}
        pending["sources"] = {"allowed": [], "constraints": {}}
        self.fixture["policy_path"].write_text(json.dumps(pending), encoding="utf-8")
        output = self.root / "must-not-exist"
        status, _, stderr = self.cli("--output-dir", str(output))
        self.assertEqual(status, 2)
        self.assertIn("BLOCKED", stderr)
        self.assertFalse(output.exists())
        with self.assertRaises(PolicyError):
            build_bundle(self.registry_path, self.corpus, pending)

    def test_check_mode_reports_registry_without_creating_candidate(self):
        status, stdout, stderr = self.cli("--check")
        self.assertEqual((status, stderr), (0, ""))
        self.assertIn("admitted=1", stdout)
        self.assertFalse(list(self.root.rglob("candidate-*")))


if __name__ == "__main__":
    unittest.main()
