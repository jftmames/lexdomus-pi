"""Audit character conservation in quarantined local copies, without publication.

This diagnostic never changes the corpus or grants source approval. It uses only
the Python standard library and the local text normalization/chunking module.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex_domus.chunking import normalize_text, split_text

BASE_COMMIT = "490de7650137ab502855c52e729aaff860aa6480"
INSPECTION_DATE = "2026-09-09"
MAX_CHARS = 1000
OVERLAP_CHARS = 120


def audit_document(path, entry):
    raw = path.read_bytes()
    normalized = normalize_text(raw.decode("utf-8"))
    chunks = split_text(normalized, max_chars=MAX_CHARS, overlap_chars=OVERLAP_CHARS)
    reconstructed = []
    previous_end = 0
    offsets_valid = True
    overlap_valid = True
    lines_valid = True
    sizes_valid = True
    content_valid = True

    for index, chunk in enumerate(chunks):
        start, end = chunk["char_start"], chunk["char_end"]
        offsets_valid &= 0 <= start < end <= len(normalized)
        offsets_valid &= start == (0 if index == 0 else previous_end - OVERLAP_CHARS)
        overlap_valid &= index == 0 or previous_end - start == OVERLAP_CHARS
        if index:
            overlap_valid &= chunks[index - 1]["text"][-OVERLAP_CHARS:] == chunk["text"][:OVERLAP_CHARS]
        content_valid &= chunk["text"] == normalized[start:end]
        sizes_valid &= 0 < len(chunk["text"]) <= MAX_CHARS
        sizes_valid &= len(chunk["text"]) == end - start
        lines_valid &= chunk["line_start"] == normalized.count("\n", 0, start) + 1
        lines_valid &= chunk["line_end"] == normalized.count("\n", 0, end - 1) + 1
        # Offsets identify only the already reconstructed prefix. Do not strip
        # whitespace or search for repeated text when removing the overlap.
        reconstructed.append(chunk["text"][previous_end - start:])
        previous_end = end

    offsets_valid &= previous_end == len(normalized)
    coverage_exact = "".join(reconstructed) == normalized
    digest = hashlib.sha256(raw).hexdigest()
    checks = {
        "registry_hash_matches": digest == entry["sha256"],
        "offsets_valid": offsets_valid,
        "overlap_valid": overlap_valid,
        "line_coordinates_valid": lines_valid,
        "chunk_sizes_valid": sizes_valid,
        "chunk_content_matches_offsets": content_valid,
    }
    return {
        "path": path.name,
        "sha256": digest,
        "byte_count": len(raw),
        "normalized_characters": len(normalized),
        "chunk_count": len(chunks),
        "max_line_chars": max(map(len, normalized.split("\n"))),
        "max_chunk_chars": max((len(chunk["text"]) for chunk in chunks), default=0),
        "coverage_exact": coverage_exact,
        "empty": not normalized,
        "registry_state": entry["state"],
        "checks": checks,
    }


def build_report():
    registry_path = ROOT / "policies/corpus-registry.json"
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    entries = {entry["path"]: entry for entry in registry["documents"]}
    corpus = ROOT / "data/corpus"
    paths = sorted(corpus.glob("*.txt"))
    if len(entries) != len(registry["documents"]):
        raise ValueError("Duplicate document paths in registry")
    if set(entries) != {path.name for path in paths}:
        raise ValueError("Registry and local TXT inventory do not match")
    documents = [audit_document(path, entries[path.name]) for path in paths]
    all_valid = all(
        document["coverage_exact"] and all(document["checks"].values())
        for document in documents
    )
    return {
        "schema_version": 1,
        "purpose": "Diagnóstico de conservación de caracteres; no publica corpus ni aprueba fuentes.",
        "inspection_date": INSPECTION_DATE,
        "base_commit": BASE_COMMIT,
        "registry": {
            "path": "policies/corpus-registry.json",
            "registry_id": registry["registry_id"],
            "revision": registry["revision"],
            "sha256": hashlib.sha256(registry_bytes).hexdigest(),
        },
        "parameters": {
            "max_chars": MAX_CHARS,
            "overlap_chars": OVERLAP_CHARS,
            "normalization": "CRLF y CR a LF; conserva todos los demás caracteres y blancos.",
            "coordinate_unit": "Unicode code points, zero-based half-open offsets; one-based inclusive lines",
        },
        "summary": {
            "document_count": len(documents),
            "nonempty_count": sum(not document["empty"] for document in documents),
            "empty_count": sum(document["empty"] for document in documents),
            "quarantined_count": sum(document["registry_state"] == "quarantined" for document in documents),
            "total_bytes": sum(document["byte_count"] for document in documents),
            "total_normalized_characters": sum(document["normalized_characters"] for document in documents),
            "total_chunks": sum(document["chunk_count"] for document in documents),
            "max_line_chars": max((document["max_line_chars"] for document in documents), default=0),
            "coverage_exact_count": sum(document["coverage_exact"] for document in documents),
            "all_checks_passed": all_valid,
            "published_documents": 0,
        },
        "documents": documents,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the diagnostic JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        destination = args.output.resolve()
        if destination.is_relative_to(ROOT / "data") or destination.is_relative_to(ROOT / "policies"):
            parser.error("Diagnostic output cannot overwrite corpus data or policies")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    return 0 if report["summary"]["all_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
