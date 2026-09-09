"""Conservative, offline ingestion. This module never promotes an active corpus."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .chunking import normalize_text, split_text
from .contracts import citation_from_record, has_text
from .policy import source_is_allowed, validate_policy


class IngestionError(ValueError):
    pass


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def _fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise IngestionError("Invalid registry fields")


def _text(value):
    return (isinstance(value, str) and bool(value.strip()) and value == value.strip()
            and not any(0xD800 <= ord(char) <= 0xDFFF for char in value))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IngestionError("Duplicate registry key")
        result[key] = value
    return result


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise IngestionError("Invalid source date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise IngestionError("Invalid source date") from exc
    if parsed > date.today():
        raise IngestionError("Future source date")
    return parsed


def _provenance(value):
    _fields(value, ("doc_id", "source", "jurisdiction", "title", "family", "ref_url",
                    "version", "version_date", "language", "retrieved_on", "content_kind",
                    "review", "reuse"))
    if any(not _text(value[key]) for key in value if key not in ("review", "reuse")):
        raise IngestionError("Incomplete source provenance")
    if value["content_kind"] != "normative_text":
        raise IngestionError("Non-normative source must remain in quarantine")
    version_date = _date(value["version_date"])
    acquired = _date(value["retrieved_on"])
    _fields(value["review"], ("reviewer", "reviewed_on", "record"))
    if any(not _text(item) for item in value["review"].values()):
        raise IngestionError("Source review is incomplete")
    reviewed = _date(value["review"]["reviewed_on"])
    if reviewed < max(version_date, acquired):
        raise IngestionError("Review predates source or acquisition")
    _fields(value["reuse"], ("basis", "record"))
    if any(not _text(item) for item in value["reuse"].values()):
        raise IngestionError("Reuse review is missing")


def inspect_registry(registry_path, corpus_dir):
    """Return admitted snapshots plus a quarantine report; never infer identity."""
    registry_path, corpus_dir = Path(registry_path), Path(corpus_dir)
    try:
        registry_bytes = registry_path.read_bytes()
        registry = json.loads(registry_bytes.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise IngestionError("Registry missing or invalid") from exc
    _fields(registry, ("schema_version", "registry_id", "revision", "documents"))
    if (type(registry["schema_version"]) is not int or registry["schema_version"] != 1
            or type(registry["revision"]) is not int or registry["revision"] < 1
            or not _text(registry["registry_id"]) or not isinstance(registry["documents"], list)):
        raise IngestionError("Invalid registry version")
    if not corpus_dir.is_dir():
        raise IngestionError("Corpus directory missing")
    admitted, quarantined, paths = [], [], set()
    for entry in registry["documents"]:
        _fields(entry, ("path", "sha256", "state", "reason", "provenance"))
        name = entry["path"]
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.txt", name)
                or name in paths or not isinstance(entry["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            raise IngestionError("Invalid or duplicate source path/hash")
        paths.add(name)
        if entry["state"] not in ("admitted", "quarantined") or not _text(entry["reason"]):
            raise IngestionError("Invalid source state")
        if entry["state"] == "quarantined" and entry["provenance"] is not None:
            raise IngestionError("Quarantine must not carry approved provenance")
        path = corpus_dir / name
        content, actual = None, None
        issue = None
        if path.is_symlink():
            issue = "symlink"
        elif not path.is_file():
            issue = "missing_or_not_regular"
        else:
            try:
                content = path.read_bytes()
                actual = digest(content)
                if actual != entry["sha256"]:
                    issue = "hash_mismatch"
            except OSError:
                issue = "unreadable"
        if entry["state"] == "quarantined":
            quarantined.append({"path": name, "reason": entry["reason"],
                                "expected_sha256": entry["sha256"], "actual_sha256": actual,
                                "integrity_issue": issue})
            continue
        _provenance(entry["provenance"])
        if issue:
            raise IngestionError("Admitted source integrity failure")
        try:
            raw = content.decode("utf-8")
        except UnicodeError as exc:
            raise IngestionError("Admitted source is not UTF-8") from exc
        if not has_text(raw):
            raise IngestionError("Admitted source is empty")
        admitted.append({"entry": entry, "raw": raw})
    for path in sorted(corpus_dir.glob("*.txt")):
        if path.name not in paths:
            quarantined.append({"path": path.name, "reason": "unregistered_source",
                                "expected_sha256": None, "actual_sha256": None,
                                "integrity_issue": None})
    return {"registry_id": registry["registry_id"], "revision": registry["revision"],
            "registry_sha256": digest(registry_bytes), "admitted": admitted,
            "quarantined": sorted(quarantined, key=lambda row: row["path"])}


def build_bundle(registry_path, corpus_dir, policy, *, max_chars=1000, overlap_chars=120):
    validate_policy(policy, "ES")
    inventory = inspect_registry(registry_path, corpus_dir)
    if not inventory["admitted"]:
        raise IngestionError("No reviewed sources")
    records, documents, duplicates, identities = [], [], [], {}
    for candidate in sorted(inventory["admitted"], key=lambda row: row["entry"]["path"]):
        entry, raw = candidate["entry"], candidate["raw"]
        provenance = entry["provenance"]
        if not source_is_allowed(policy, provenance):
            raise IngestionError("Admitted source outside policy")
        identity = (provenance["doc_id"], provenance["version"])
        signature = (entry["sha256"], canonical_json(provenance))
        if identity in identities:
            previous = identities[identity]
            if previous["signature"] != signature:
                raise IngestionError("Conflicting copies of one document version")
            duplicates.append({"path": entry["path"], "canonical_path": previous["path"],
                               "doc_id": identity[0], "version": identity[1], "sha256": entry["sha256"]})
            continue
        identities[identity] = {"signature": signature, "path": entry["path"]}
        normalized = normalize_text(raw)
        normalized_hash = digest(normalized.encode("utf-8"))
        pieces = split_text(raw, max_chars=max_chars, overlap_chars=overlap_chars)
        covered, previous_start = 0, -1
        for part in pieces:
            start, end = part["char_start"], part["char_end"]
            if (start <= previous_start or start > covered or not 0 <= start < end <= len(normalized)
                    or end <= covered or end - start > max_chars or part["text"] != normalized[start:end]):
                raise IngestionError("Text coverage failure")
            covered, previous_start = end, start
            chunk_id = digest(canonical_json({"doc_id": identity[0], "version": identity[1],
                                             "source_sha256": entry["sha256"], "start": start, "end": end}))
            record = {key: provenance[key] for key in ("doc_id", "source", "jurisdiction", "title", "family", "ref_url")}
            record.update(part, chunk_id=chunk_id, document_version=provenance["version"],
                          source_sha256=entry["sha256"], normalized_sha256=normalized_hash,
                          ref_label=f"{provenance['title']} — copia {provenance['version']}", pinpoint=False)
            if has_text(part["text"]) and citation_from_record(record) is None:
                raise IngestionError("Invalid generated citation")
            records.append(record)
        if covered != len(normalized):
            raise IngestionError("Incomplete text coverage")
        documents.append({"path": entry["path"], "provenance": provenance,
                          "source_sha256": entry["sha256"], "normalized_sha256": normalized_hash,
                          "normalized_characters": len(normalized), "covered_characters": covered,
                          "chunk_count": len(pieces)})
    chunks = b"".join(canonical_json(record) for record in records)
    manifest = {"schema_version": 1, "registry_id": inventory["registry_id"],
                "registry_revision": inventory["revision"], "registry_sha256": inventory["registry_sha256"],
                "policy_id": policy["policy_id"], "policy_revision": policy["revision"],
                "policy_sha256": digest(canonical_json(policy)),
                "normalization": "CRLF/CR to LF only; Unicode code-point offsets, half-open",
                "chunking": {"max_chars": max_chars, "overlap_chars": overlap_chars},
                "chunks_sha256": digest(chunks), "chunk_count": len(records), "documents": documents,
                "duplicates": duplicates, "quarantined": inventory["quarantined"]}
    manifest["corpus_id"] = digest(canonical_json(manifest))
    return chunks, canonical_json(manifest)


def save_candidate(parent, chunks, manifest):
    """Each build gets a new isolated directory; existing artifacts are untouched."""
    parent = Path(parent)
    try:
        parent.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix="candidate-", dir=parent))
    except OSError as exc:
        raise IngestionError("Cannot create candidate directory") from exc
    try:
        (destination / "chunks.jsonl").write_bytes(chunks)
        (destination / "manifest.json").write_bytes(manifest)
    except OSError as exc:
        shutil.rmtree(destination)
        raise IngestionError("Cannot finish candidate") from exc
    return destination
