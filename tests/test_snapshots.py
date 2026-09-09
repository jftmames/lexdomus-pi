"""Acceptance tests for pinned evidence, using only synthetic offline material.

Resealing in selected adversarial cases represents an internally inconsistent
candidate, not permission to replace the externally selected production pin.
"""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.pipeline import analyze_clause
from lex_domus import rag_pipeline, retriever, snapshots
from lex_domus.ingestion import build_bundle, canonical_json, digest, save_candidate
from lex_domus.policy import PolicyError
from tests.snapshot_fixtures import create_snapshot_fixture, snapshot_environment
from tests.test_api import asgi_request
from tests.test_ingestion import synthetic_provenance


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lexdomus-snapshot-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "llm.provider.call_llm_json"):
            guard = Mock(side_effect=AssertionError("External requests forbidden in snapshot tests"))
            self._patch(target, guard)
            self.addCleanup(guard.assert_not_called)
        self.fixture = create_snapshot_fixture(self.root,
            ("\ufeffDerechos patrimoniales y morales: licencia editorial sintética. 😀\r\n" * 11).encode("utf-8"),
            max_chars=130, overlap_chars=20)
        self.policy = self.fixture["policy"]
        self.directory = self.fixture["snapshot"]
        self._patch("lex_domus.snapshots.REGISTRY_PATH", self.fixture["registry_path"])
        self._patch("lex_domus.rag_pipeline.POLICY_PATH", self.fixture["policy_path"])
        self._patch("metrics_eee.logger.append_log", Mock())
        patcher = patch.dict(os.environ, snapshot_environment(self.fixture), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch(self, target, value):
        patcher = patch(target, value)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def load(self):
        return snapshots.load_active_snapshot(self.policy)

    def clone(self):
        parent = Path(tempfile.mkdtemp(prefix="variant-", dir=self.root))
        destination = parent / "snapshot"
        shutil.copytree(self.directory, destination)
        return destination

    def select(self, directory):
        descriptor = json.loads((directory / "snapshot.json").read_bytes())
        return patch.dict(os.environ, {"LEXDOMUS_SNAPSHOT_DIR": str(directory),
                                       "LEXDOMUS_SNAPSHOT_ID": descriptor["snapshot_id"]})

    def repin(self, directory, descriptor):
        descriptor = {key: value for key, value in descriptor.items() if key != "snapshot_id"}
        descriptor["snapshot_id"] = digest(canonical_json(descriptor))
        (directory / "snapshot.json").write_bytes(canonical_json(descriptor))

    def reseal(self, directory, *, records=None, manifest=None):
        """Update outer checksums so deeper invariants receive the malformed data."""
        if records is not None:
            (directory / "chunks.jsonl").write_bytes(b"".join(canonical_json(row) for row in records))
        if manifest is None:
            manifest = json.loads((directory / "manifest.json").read_bytes())
        manifest["chunks_sha256"] = digest((directory / "chunks.jsonl").read_bytes())
        manifest.pop("corpus_id", None)
        manifest["corpus_id"] = digest(canonical_json(manifest))
        (directory / "manifest.json").write_bytes(canonical_json(manifest))
        descriptor = json.loads((directory / "snapshot.json").read_bytes())
        descriptor.update(corpus_id=manifest["corpus_id"],
                          chunks_sha256=manifest["chunks_sha256"],
                          manifest_sha256=digest(canonical_json(manifest)))
        self.repin(directory, descriptor)

    def assert_unavailable(self, directory):
        with self.select(directory), self.assertRaises(snapshots.CorpusError):
            self.load()

    def test_reproducible_snapshot_and_mutation_safe_search(self):
        other = snapshots.prepare_snapshot(self.fixture["candidate"], self.root / "snapshots",
                                            self.policy, self.fixture["registry_path"], corpus_dir=self.fixture["corpus"])
        self.assertNotEqual(other, self.directory)
        for name in ("chunks.jsonl", "manifest.json", "snapshot.json"):
            self.assertEqual((other / name).read_bytes(), (self.directory / name).read_bytes())
        verified = self.load()
        context = verified.context()
        self.assertEqual(context["mode"], "lexical-overlap-v1")
        self.assertEqual(context["active_indices"], [])
        self.assertEqual(context["snapshot_id"], self.fixture["descriptor"]["snapshot_id"])
        self.assertEqual(context["corpus_id"], json.loads(self.fixture["manifest_bytes"])["corpus_id"])
        found = verified.search("derechos licencia", 3, self.policy)
        self.assertTrue(found)
        before = deepcopy(found)
        found[0]["text"] = "Injected synthetic text"
        found[0]["meta"]["doc_id"] = "different-document"
        context["active_indices"].append("FAISS")
        self.assertEqual(verified.search("derechos licencia", 3, self.policy), before)
        self.assertEqual(verified.context()["active_indices"], [])
        self.assertEqual(verified.search("inexistenteqwerty", 3, self.policy), [])
        self.assertEqual(verified.search("derechos", 0, self.policy), [])
        self.assertEqual(verified.search("  ", 3, self.policy), [])
        for query, limit in ((None, 1), ("derechos", True), ("derechos", -1)):
            with self.subTest(query=query, limit=limit), self.assertRaises(ValueError):
                verified.search(query, limit, self.policy)

    def test_selection_requires_absolute_directory_and_exact_external_pin(self):
        variants = ({"LEXDOMUS_SNAPSHOT_DIR": ""}, {"LEXDOMUS_SNAPSHOT_DIR": "relative/path"},
                    {"LEXDOMUS_SNAPSHOT_DIR": str(self.root / "missing")},
                    {"LEXDOMUS_SNAPSHOT_ID": ""}, {"LEXDOMUS_SNAPSHOT_ID": "x" * 64},
                    {"LEXDOMUS_SNAPSHOT_ID": "0" * 64})
        for values in variants:
            with self.subTest(values=values), patch.dict(os.environ, values), self.assertRaises(snapshots.CorpusError):
                self.load()

    def test_absent_or_corrupt_snapshot_files_are_rejected(self):
        for name in ("chunks.jsonl", "manifest.json", "snapshot.json"):
            for mutation in ("missing", "empty", "malformed", "unhashed-byte"):
                with self.subTest(name=name, mutation=mutation):
                    directory = self.clone()
                    pin = self.fixture["descriptor"]["snapshot_id"]
                    target = directory / name
                    if mutation == "missing":
                        target.unlink()
                    else:
                        target.write_bytes({"empty": b"", "malformed": b"{invalid-json",
                                            "unhashed-byte": target.read_bytes() + b" "}[mutation])
                    with patch.dict(os.environ, {"LEXDOMUS_SNAPSHOT_DIR": str(directory),
                                                  "LEXDOMUS_SNAPSHOT_ID": pin}), self.assertRaises(snapshots.CorpusError):
                        self.load()

    def test_descriptor_cannot_claim_unverified_modes_or_indices(self):
        variants = ({"mode": "faiss"}, {"mode": "bm25"}, {"active_indices": ["bm25.pkl"]},
                    {"active_indices": {}}, {"schema_version": True}, {"corpus_id": "0" * 64},
                    {"unrecognized": "field"})
        for values in variants:
            with self.subTest(values=values):
                directory = self.clone()
                descriptor = json.loads((directory / "snapshot.json").read_bytes())
                self.repin(directory, {**descriptor, **values})
                self.assert_unavailable(directory)

    def test_manifest_and_provenance_are_verified_beyond_outer_hashes(self):
        variants = ({"policy_revision": 2}, {"registry_id": "other-registry"},
                    {"chunk_count": True}, {"normalization": "strip-and-collapse"},
                    {"chunking": {"max_chars": 130, "overlap_chars": 130}},
                    {"documents": []}, {"duplicates": [{"path": "invented.txt"}]},
                    {"quarantined": [{"path": "undeclared.txt"}]})
        for values in variants:
            with self.subTest(values=values):
                directory = self.clone()
                manifest = json.loads((directory / "manifest.json").read_bytes())
                self.reseal(directory, manifest={**manifest, **values})
                self.assert_unavailable(directory)

    def test_record_coordinates_identity_and_overlap_cannot_be_forged(self):
        variants = ({"char_start": True}, {"char_end": 131}, {"line_start": 99},
                    {"source_sha256": "0" * 64}, {"normalized_sha256": "0" * 64},
                    {"chunk_id": "0" * 64}, {"document_version": "invented-version"},
                    {"ref_url": "https://unapproved.invalid/source"}, {"pinpoint": True},
                    {"title": "Invented synthetic title"})
        original = [json.loads(line) for line in self.fixture["chunks_bytes"].splitlines()]
        for values in variants:
            with self.subTest(values=values):
                directory = self.clone()
                records = deepcopy(original)
                records[0].update(values)
                self.reseal(directory, records=records)
                self.assert_unavailable(directory)
        for mutation in ("missing", "duplicated", "reordered", "overlap-text"):
            with self.subTest(mutation=mutation):
                directory = self.clone()
                records = deepcopy(original)
                if mutation == "missing":
                    records.pop(1)
                elif mutation == "duplicated":
                    records.insert(1, deepcopy(records[0]))
                elif mutation == "reordered":
                    records.reverse()
                else:
                    records[1]["text"] = "X" + records[1]["text"][1:]
                manifest = json.loads(self.fixture["manifest_bytes"])
                manifest["chunk_count"] = len(records)
                self.reseal(directory, records=records, manifest=manifest)
                self.assert_unavailable(directory)

    def test_policy_and_registry_changes_invalidate_selected_evidence(self):
        verified = self.load()
        changed_policy = deepcopy(self.policy)
        changed_policy["revision"] += 1
        with self.assertRaises(snapshots.CorpusError):
            snapshots.load_active_snapshot(changed_policy)
        with self.assertRaises(snapshots.CorpusError):
            verified.search("derechos", 3, changed_policy)
        pending = deepcopy(self.policy)
        pending["review"]["status"] = "pending"
        with self.assertRaises(PolicyError):
            verified.search("derechos", 3, pending)
        original = self.fixture["registry_path"].read_bytes()
        for value in (b"", original + b" ", b"{\"schema_version\": 1, \"schema_version\": 1}"):
            with self.subTest(value_length=len(value)):
                self.fixture["registry_path"].write_bytes(value)
                with self.assertRaises(snapshots.CorpusError):
                    self.load()
        self.fixture["registry_path"].write_bytes(original)
        registry = deepcopy(self.fixture["registry"])
        registry["documents"][0]["sha256"] = "0" * 64
        self.fixture["registry_path"].write_bytes(canonical_json(registry))
        with self.assertRaises(snapshots.CorpusError):
            self.load()

    def test_extra_files_and_links_are_never_loaded(self):
        for name in ("bm25.pkl", "faiss.index", "unregistered.txt"):
            with self.subTest(extra=name):
                directory = self.clone()
                (directory / name).write_bytes(b"Not an index; synthetic untrusted bytes")
                self.assert_unavailable(directory)
        for name in ("chunks.jsonl", "manifest.json", "snapshot.json"):
            with self.subTest(symlink=name):
                directory = self.clone()
                target = directory / name
                target.unlink()
                target.symlink_to(self.directory / name)
                with patch.dict(os.environ, {"LEXDOMUS_SNAPSHOT_DIR": str(directory)}), self.assertRaises(snapshots.CorpusError):
                    self.load()
        link = self.root / "linked-snapshot"
        link.symlink_to(self.directory, target_is_directory=True)
        with patch.dict(os.environ, {"LEXDOMUS_SNAPSHOT_DIR": str(link)}), self.assertRaises(snapshots.CorpusError):
            self.load()
        saved_registry = self.fixture["registry_path"].with_suffix(".saved")
        self.fixture["registry_path"].rename(saved_registry)
        self.fixture["registry_path"].symlink_to(saved_registry)
        with self.assertRaises(snapshots.CorpusError):
            self.load()

    def test_failed_preparation_preserves_sources_and_existing_candidates(self):
        watched = [self.fixture["source"], self.fixture["registry_path"],
                   *self.fixture["candidate"].iterdir(), *self.directory.iterdir()]
        before = {path: path.read_bytes() for path in watched}
        prior_directories = set((self.root / "snapshots").iterdir())
        bad = self.root / "bad-candidate"
        shutil.copytree(self.fixture["candidate"], bad)
        (bad / "chunks.jsonl").write_bytes(b"corrupt synthetic candidate")
        with self.assertRaises(snapshots.CorpusError):
            snapshots.prepare_snapshot(bad, self.root / "snapshots", self.policy, self.fixture["registry_path"],
                                       corpus_dir=self.fixture["corpus"])
        original_write = Path.write_bytes

        def fail_descriptor(path, content):
            if path.name == "snapshot.json":
                raise OSError("Synthetic disk-full failure")
            return original_write(path, content)

        with patch.object(Path, "write_bytes", fail_descriptor), self.assertRaises(snapshots.CorpusError):
            snapshots.prepare_snapshot(self.fixture["candidate"], self.root / "snapshots",
                                       self.policy, self.fixture["registry_path"], corpus_dir=self.fixture["corpus"])
        self.assertEqual(set((self.root / "snapshots").iterdir()), prior_directories)
        self.assertEqual({path: path.read_bytes() for path in watched}, before)
        self.assertEqual(os.environ["LEXDOMUS_SNAPSHOT_ID"], self.fixture["descriptor"]["snapshot_id"])

    def test_preparation_checks_actual_sources_against_a_coherently_rewritten_candidate(self):
        # Build a second internally consistent document with the same fictional
        # identity, then falsely attribute its text to the first source hash.
        alternative = create_snapshot_fixture(self.root / "alternative-source",
            b"Contenido sintetico sustituido completamente; derechos editoriales falsificados.\n",
            max_chars=130, overlap_chars=20)
        records = [json.loads(line) for line in alternative["chunks_bytes"].splitlines()]
        original_hash = self.fixture["registry"]["documents"][0]["sha256"]
        for record in records:
            record["source_sha256"] = original_hash
            record["chunk_id"] = digest(canonical_json({
                "doc_id": record["doc_id"], "version": record["document_version"],
                "source_sha256": original_hash, "start": record["char_start"], "end": record["char_end"],
            }))
        chunks = b"".join(canonical_json(record) for record in records)
        manifest = json.loads(alternative["manifest_bytes"])
        manifest["registry_sha256"] = digest(self.fixture["registry_path"].read_bytes())
        manifest["documents"][0]["source_sha256"] = original_hash
        manifest["chunks_sha256"] = digest(chunks)
        manifest.pop("corpus_id")
        manifest["corpus_id"] = digest(canonical_json(manifest))
        forged = save_candidate(self.root / "candidates", chunks, canonical_json(manifest))
        before = set((self.root / "snapshots").iterdir())
        with self.assertRaises(snapshots.CorpusError):
            snapshots.prepare_snapshot(forged, self.root / "snapshots", self.policy,
                                       self.fixture["registry_path"], corpus_dir=self.fixture["corpus"])
        self.assertEqual(set((self.root / "snapshots").iterdir()), before)

    def test_preparation_rejects_changed_originals_and_undeclared_candidate_files(self):
        before = self.fixture["source"].read_bytes()
        for mutation in ("source-content", "source-missing", "candidate-extra-file"):
            with self.subTest(mutation=mutation):
                directory = Path(tempfile.mkdtemp(prefix="candidate-check-", dir=self.root))
                candidate = directory / "candidate"
                shutil.copytree(self.fixture["candidate"], candidate)
                if mutation == "source-content":
                    self.fixture["source"].write_bytes(b"Different synthetic original source")
                elif mutation == "source-missing":
                    self.fixture["source"].unlink()
                else:
                    (candidate / "bm25.pkl").write_bytes(b"Unrequested synthetic index")
                with self.assertRaises(snapshots.CorpusError):
                    snapshots.prepare_snapshot(candidate, self.root / "snapshots", self.policy,
                                               self.fixture["registry_path"], corpus_dir=self.fixture["corpus"])
                self.fixture["source"].write_bytes(before)

    def test_identical_copies_collapse_but_documents_and_versions_remain_distinct(self):
        registry = deepcopy(self.fixture["registry"])
        for name, provenance in (("alias.txt", synthetic_provenance()),
                                 ("other.txt", synthetic_provenance("different-document")),
                                 ("version.txt", synthetic_provenance(version="synthetic-v2"))):
            entry = deepcopy(registry["documents"][0])
            entry.update(path=name, provenance=provenance)
            registry["documents"].append(entry)
            (self.fixture["corpus"] / name).write_bytes(self.fixture["source"].read_bytes())
        self.fixture["registry_path"].write_bytes(canonical_json(registry))
        chunks, manifest = build_bundle(self.fixture["registry_path"], self.fixture["corpus"], self.policy)
        candidate = save_candidate(self.root / "candidates", chunks, manifest)
        directory = snapshots.prepare_snapshot(candidate, self.root / "snapshots", self.policy,
                                               self.fixture["registry_path"], corpus_dir=self.fixture["corpus"])
        with self.select(directory):
            found = self.load().search("derechos", 10, self.policy)
        identities = {(row["meta"]["doc_id"], row["meta"]["document_version"]) for row in found}
        self.assertEqual(identities, {("synthetic-editorial", "synthetic-v1"),
                                      ("synthetic-editorial", "synthetic-v2"),
                                      ("different-document", "synthetic-v1")})
        self.assertEqual(len(found), 3)
        self.assertEqual(len(json.loads(manifest)["duplicates"]), 1)

    def test_one_request_uses_one_snapshot_and_next_request_detects_disk_change(self):
        original_answer = rag_pipeline.source_required_answer
        original_load = snapshots.load_active_snapshot
        altered = False

        def change_after_first_node(*args, **kwargs):
            nonlocal altered
            result = original_answer(*args, **kwargs)
            if not altered:
                altered = True
                (self.directory / "chunks.jsonl").write_bytes(b"Changed between inquiry nodes")
            return result

        with patch.object(snapshots, "load_active_snapshot", wraps=original_load) as loader, patch.object(
            rag_pipeline, "source_required_answer", side_effect=change_after_first_node
        ) as answer, patch("app.writer_llm.draft_opinion_llm", return_value={"analysis_md": "Synthetic draft"}) as writer:
            result = analyze_clause("Licencia editorial sintética con derechos patrimoniales y morales.", "ES")
            self.assertTrue(altered)
            self.assertGreater(len(result["per_node"]), 1)
            self.assertEqual(loader.call_count, 1)
            selected = [call.kwargs["snapshot"] for call in answer.call_args_list]
            self.assertTrue(all(item is selected[0] for item in selected))
            self.assertEqual(result["retrieval_context"]["snapshot_id"], self.fixture["descriptor"]["snapshot_id"])
            citations = [citation for node in result["per_node"] for citation in node["retrieval"]["citations"]]
            self.assertTrue(citations)
            self.assertTrue(all("Changed between" not in row["text"] for row in citations))
            writer.assert_called_once()
            calls_before = answer.call_count
            with self.assertRaises(snapshots.CorpusError):
                analyze_clause("Segunda consulta sintética", "ES")
            self.assertEqual(loader.call_count, 2)
            self.assertEqual(answer.call_count, calls_before)
            writer.assert_called_once()

    def test_missing_snapshot_blocks_http_and_direct_paths_before_processing(self):
        clause = "SYNTHETIC-PRIVATE-MARKER-42 licencia editorial"
        with patch.dict(os.environ, {"LEXDOMUS_SNAPSHOT_ID": ""}), patch(
            "app.writer_llm.draft_opinion_llm"
        ) as writer, patch("verdiktia.inquiry_engine.decompose_clause") as inquiry, self.assertLogs("api.main", level="WARNING") as logs:
            status, body = asyncio.run(asgi_request({"clause": clause, "jurisdiction": "ES"}))
            self.assertEqual(status, 503)
            self.assertEqual(body["status"], "TECHNICAL_ERROR")
            self.assertNotIn(clause, json.dumps(body))
            self.assertNotIn(str(self.root), json.dumps(body))
            self.assertNotIn(clause, "\n".join(logs.output))
            for operation in (lambda: analyze_clause(clause, "ES"),
                              lambda: retriever.retrieve_candidates(clause, policy=self.policy),
                              lambda: rag_pipeline.source_required_answer(clause, jurisdiction="ES", policy=self.policy)):
                with self.assertRaises(snapshots.CorpusError):
                    operation()
            writer.assert_not_called()
            inquiry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
