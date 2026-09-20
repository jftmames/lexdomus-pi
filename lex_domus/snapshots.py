"""Offline, pinned corpus snapshots for the lexical retriever.

Hashes establish correspondence with recorded bytes, not legal authenticity.
No persisted search index, pickle, embedding model or network client is loaded.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import stat

from .chunking import normalize_text, split_text
from .contracts import citation_from_record, has_text
from .ingestion import build_bundle, canonical_json, chunk_record, digest, parse_registry, save_candidate
from .policy import source_is_allowed, validate_policy

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "policies/corpus-registry.json"
MODE = "lexical-overlap-v1"
MAX_FILE_BYTES = 32 * 1024 * 1024
_WORD = re.compile(r"\w+", re.U)
_HASH = re.compile(r"[0-9a-f]{64}")
_MANIFEST_FIELDS = {"schema_version", "registry_id", "registry_revision", "registry_sha256",
                    "policy_id", "policy_revision", "policy_sha256", "normalization", "chunking",
                    "chunks_sha256", "chunk_count", "documents", "duplicates", "quarantined", "corpus_id"}
_DESCRIPTOR_FIELDS = {"schema_version", "mode", "active_indices", "corpus_id",
                      "manifest_sha256", "chunks_sha256", "snapshot_id"}


class CorpusError(ValueError):
    """Unavailable or inconsistent evidence; callers must abstain."""


def _require(condition):
    if not condition:
        raise CorpusError("Corpus snapshot verification failed")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _json(content):
    def invalid_constant(_value):
        raise CorpusError("Invalid JSON constant")
    return json.loads(content.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=invalid_constant)


def _read_fd(fd):
    with os.fdopen(fd, "rb") as stream:
        _require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode))
        content = stream.read(MAX_FILE_BYTES + 1)
        _require(len(content) <= MAX_FILE_BYTES)
        return content


def _read_file(path):
    return _read_fd(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK))


def _read_directory(directory, names):
    # Capture all files through the same directory descriptor. Renaming the
    # selected directory during a read cannot select a different parent midway.
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _require(set(os.listdir(fd)) == set(names))
        return {name: _read_fd(os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                       dir_fd=fd)) for name in names}
    finally:
        os.close(fd)


def tokenize(text):
    return frozenset(_WORD.findall(text.lower()))


def _verify_corpus(chunks_bytes, manifest_bytes, registry_bytes, policy):
    manifest = _json(manifest_bytes)
    _require(isinstance(manifest, dict) and set(manifest) == _MANIFEST_FIELDS)
    _require(manifest_bytes == canonical_json(manifest))
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1)
    unsigned = {key: value for key, value in manifest.items() if key != "corpus_id"}
    _require(manifest["corpus_id"] == digest(canonical_json(unsigned)))
    _require(manifest["chunks_sha256"] == digest(chunks_bytes))
    registry = parse_registry(registry_bytes)
    _require(manifest["registry_sha256"] == digest(registry_bytes))
    _require(manifest["registry_id"] == registry["registry_id"])
    _require(type(manifest["registry_revision"]) is int and manifest["registry_revision"] == registry["revision"])
    _require(manifest["policy_sha256"] == digest(canonical_json(policy)))
    _require(manifest["policy_id"] == policy["policy_id"])
    _require(type(manifest["policy_revision"]) is int and manifest["policy_revision"] == policy["revision"])
    _require(manifest["normalization"] == "CRLF/CR to LF only; Unicode code-point offsets, half-open")
    params = manifest["chunking"]
    _require(isinstance(params, dict) and set(params) == {"max_chars", "overlap_chars"})
    split_text("", **params)  # Validate strict integer sizes and forward progress.
    records = [_json(line) for line in chunks_bytes.splitlines()]
    _require(records and type(manifest["chunk_count"]) is int and manifest["chunk_count"] == len(records))
    grouped = {}
    for record in records:
        _require(isinstance(record, dict) and isinstance(record.get("text"), str))
        identity = (record.get("doc_id"), record.get("document_version"))
        _require(all(isinstance(value, str) and has_text(value) for value in identity))
        grouped.setdefault(identity, []).append(record)

    identities, duplicates, documents, expected_records = {}, [], [], []
    for entry in sorted(registry["documents"], key=lambda item: item["path"]):
        if entry["state"] != "admitted":
            continue
        provenance = entry["provenance"]
        _require(source_is_allowed(policy, provenance))
        identity = (provenance["doc_id"], provenance["version"])
        signature = (entry["sha256"], canonical_json(provenance))
        if identity in identities:
            previous = identities[identity]
            _require(previous["signature"] == signature)
            duplicates.append({"path": entry["path"], "canonical_path": previous["path"],
                               "doc_id": identity[0], "version": identity[1], "sha256": entry["sha256"]})
            continue
        identities[identity] = {"signature": signature, "path": entry["path"]}
        pieces = grouped.pop(identity, [])
        _require(bool(pieces))
        recovered, covered = [], 0
        for piece in pieces:
            start, end, text = piece.get("char_start"), piece.get("char_end"), piece["text"]
            _require(type(start) is int and type(end) is int)
            _require(0 <= start <= covered < end and end - start == len(text))
            _require(len(text) <= params["max_chars"])
            recovered.append(text[covered - start:])
            covered = end
        normalized = "".join(recovered)
        _require(has_text(normalized) and normalize_text(normalized) == normalized)
        normalized_hash = digest(normalized.encode("utf-8"))
        # Recreate the complete expected records from the recovered source and
        # the trusted registry. This checks text in overlaps, all coordinates,
        # IDs, labels and every provenance field, including record order.
        expected = [chunk_record(provenance, entry["sha256"], normalized_hash, part)
                    for part in split_text(normalized, **params)]
        _require(canonical_json(pieces) == canonical_json(expected))
        expected_records.extend(expected)
        documents.append({"path": entry["path"], "provenance": provenance,
                          "source_sha256": entry["sha256"], "normalized_sha256": normalized_hash,
                          "normalized_characters": len(normalized), "covered_characters": covered,
                          "chunk_count": len(expected)})
    _require(not grouped and bool(documents))
    _require(chunks_bytes == b"".join(canonical_json(record) for record in expected_records))
    _require(canonical_json(manifest["documents"]) == canonical_json(documents))
    _require(canonical_json(manifest["duplicates"]) == canonical_json(duplicates))
    _verify_quarantine(manifest["quarantined"], registry)
    return records, manifest


def _verify_quarantine(rows, registry):
    _require(isinstance(rows, list))
    entries = {entry["path"]: entry for entry in registry["documents"]}
    seen = set()
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {"path", "reason", "expected_sha256", "actual_sha256", "integrity_issue"})
        path = row["path"]
        _require(isinstance(path, str) and Path(path).name == path and path.endswith(".txt") and "\0" not in path)
        _require(path not in seen)
        seen.add(path)
        entry = entries.get(path)
        if entry is None:
            _require(row == {"path": path, "reason": "unregistered_source", "expected_sha256": None,
                             "actual_sha256": None, "integrity_issue": None})
        else:
            _require(entry["state"] == "quarantined" and row["reason"] == entry["reason"])
            _require(row["expected_sha256"] == entry["sha256"])
            actual, issue = row["actual_sha256"], row["integrity_issue"]
            _require(actual is None or (isinstance(actual, str) and _HASH.fullmatch(actual)))
            _require(issue in (None, "symlink", "missing_or_not_regular", "hash_mismatch", "unreadable"))
            if issue is None:
                _require(actual == entry["sha256"])
            elif issue == "hash_mismatch":
                _require(actual is not None and actual != entry["sha256"])
            else:
                _require(actual is None)
    _require({entry["path"] for entry in entries.values() if entry["state"] == "quarantined"} <= seen)


@dataclass(frozen=True)
class VerifiedSnapshot:
    """Immutable strings and token sets; callers receive fresh citation objects."""
    snapshot_id: str
    corpus_id: str
    policy_sha256: str
    _citations: tuple
    _tokens: tuple

    def context(self):
        return {"mode": MODE, "snapshot_id": self.snapshot_id,
                "corpus_id": self.corpus_id, "active_indices": []}

    def search(self, query, k, policy):
        validate_policy(policy)
        _require(digest(canonical_json(policy)) == self.policy_sha256)
        if not isinstance(query, str) or type(k) is not int or k < 0:
            raise ValueError("Invalid retrieval query or limit")
        query_tokens = tokenize(query)
        if not query_tokens or k == 0:
            return []
        ranked = sorted(((len(query_tokens & tokens), i) for i, tokens in enumerate(self._tokens)),
                        key=lambda pair: (-pair[0], pair[1]))
        result, seen = [], set()
        for score, index in ranked:
            if score == 0:
                break
            citation = json.loads(self._citations[index])
            if not source_is_allowed(policy, citation["meta"]):
                continue
            meta = citation["meta"]
            identity = (meta["doc_id"], meta["document_version"], citation["text"])
            if identity in seen:
                continue
            seen.add(identity)
            result.append(citation)
            if len(result) == k:
                break
        return result


def _snapshot(records, manifest, descriptor, policy):
    citations = [citation_from_record(record) for record in records if has_text(record["text"])]
    _require(citations and all(citation is not None for citation in citations))
    return VerifiedSnapshot(descriptor["snapshot_id"], manifest["corpus_id"], digest(canonical_json(policy)),
                            tuple(canonical_json(citation).decode("utf-8") for citation in citations),
                            tuple(tokenize(citation["text"]) for citation in citations))


def prepare_snapshot(candidate_dir, output_dir, policy, registry_path, *, corpus_dir):
    """Write a new verified candidate; never select or replace active evidence."""
    validate_policy(policy)
    destination = None
    try:
        files = _read_directory(candidate_dir, ("chunks.jsonl", "manifest.json"))
        records, manifest = _verify_corpus(files["chunks.jsonl"], files["manifest.json"], _read_file(registry_path), policy)
        # Preparation must prove that the candidate text came from originals
        # matching the registry, not merely trust its claimed source hashes.
        rebuilt_chunks, rebuilt_manifest = build_bundle(registry_path, corpus_dir, policy, **manifest["chunking"])
        _require(files["chunks.jsonl"] == rebuilt_chunks and files["manifest.json"] == rebuilt_manifest)
        descriptor = {"schema_version": 1, "mode": MODE, "active_indices": [],
                      "corpus_id": manifest["corpus_id"], "manifest_sha256": digest(files["manifest.json"]),
                      "chunks_sha256": digest(files["chunks.jsonl"])}
        descriptor["snapshot_id"] = digest(canonical_json(descriptor))
        _snapshot(records, manifest, descriptor, policy)
        destination = save_candidate(output_dir, files["chunks.jsonl"], files["manifest.json"])
        (destination / "snapshot.json").write_bytes(canonical_json(descriptor))
        return destination
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        if destination is not None:
            shutil.rmtree(destination)
        raise CorpusError("Cannot prepare verified snapshot") from exc


def load_active_snapshot(policy):
    """Load one explicitly selected and pinned snapshot, without legacy fallback."""
    return load_snapshot(policy, os.environ.get("LEXDOMUS_SNAPSHOT_DIR", ""),
                         os.environ.get("LEXDOMUS_SNAPSHOT_ID", ""), REGISTRY_PATH)


def load_snapshot(policy, directory, expected_id, registry_path):
    """Verify an explicitly supplied context without changing process configuration."""
    validate_policy(policy)
    try:
        _require(bool(directory) and Path(directory).is_absolute() and bool(_HASH.fullmatch(expected_id)))
        files = _read_directory(directory, ("snapshot.json", "manifest.json", "chunks.jsonl"))
        descriptor = _json(files["snapshot.json"])
        _require(isinstance(descriptor, dict) and set(descriptor) == _DESCRIPTOR_FIELDS)
        _require(files["snapshot.json"] == canonical_json(descriptor))
        _require(type(descriptor["schema_version"]) is int and descriptor["schema_version"] == 1)
        _require(descriptor["mode"] == MODE and descriptor["active_indices"] == [])
        unsigned = {key: value for key, value in descriptor.items() if key != "snapshot_id"}
        _require(descriptor["snapshot_id"] == expected_id == digest(canonical_json(unsigned)))
        _require(descriptor["manifest_sha256"] == digest(files["manifest.json"]))
        _require(descriptor["chunks_sha256"] == digest(files["chunks.jsonl"]))
        records, manifest = _verify_corpus(files["chunks.jsonl"], files["manifest.json"], _read_file(registry_path), policy)
        _require(descriptor["corpus_id"] == manifest["corpus_id"])
        return _snapshot(records, manifest, descriptor, policy)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise CorpusError("Active evidence unavailable") from exc
