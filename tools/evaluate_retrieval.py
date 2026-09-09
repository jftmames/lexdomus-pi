"""Reproduce eight synthetic lexical-retrieval cases without network or models.

These deliberately tiny fixtures test mechanics, including a known synonym
miss. They are not legal sources, a law-firm evaluation or a quality target.
"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex_domus.contracts import citation_from_record
from lex_domus.ingestion import build_bundle, canonical_json, digest, save_candidate
from lex_domus.policy import source_is_allowed
from lex_domus.snapshots import load_active_snapshot, prepare_snapshot

BASE_COMMIT = "7dc5cceb43fff5c3b4db3c73a23d15e3fe9c6b0d"
EVALUATION_DATE = "2026-09-09"
EVIDENCE_PATH = ROOT / "docs/T06-evidence/retrieval.json"
TOP_K = 3
DOCUMENTS = (
    ("synthetic-plazo", "Plazo ficticio", "Cláusula ficticia P: duración plazo vigencia meses.\n"),
    ("synthetic-remuneracion", "Remuneración ficticia", "Cláusula ficticia R: remuneración importe euros anticipo.\n"),
    ("synthetic-territorio", "Territorio ficticio", "Cláusula ficticia T: territorio España países distribución.\n"),
    ("synthetic-exclusividad", "Exclusividad ficticia", "Cláusula ficticia E: exclusividad exclusiva licencia editorial.\n"),
    ("synthetic-morales", "Derechos morales ficticios", "Cláusula ficticia M: atribución autoría integridad derechos morales.\n"),
)
# Explicit reference answers are fixed before running retrieval. They express
# the intended topic of each fictional fixture, not a legal interpretation.
QUERIES = (
    ("Q01", "literal", "plazo duración vigencia", ("synthetic-plazo",)),
    ("Q02", "literal", "remuneración importe", ("synthetic-remuneracion",)),
    ("Q03", "literal", "territorio países", ("synthetic-territorio",)),
    ("Q04", "literal", "exclusividad licencia", ("synthetic-exclusividad",)),
    ("Q05", "literal", "autoría integridad", ("synthetic-morales",)),
    ("Q06", "stable_tie", "plazo remuneración", ("synthetic-plazo", "synthetic-remuneracion")),
    ("Q07", "synonym_without_lexical_overlap", "límite temporal", ("synthetic-plazo",)),
    ("Q08", "outside_fixture_corpus", "arbitraje marítimo", ()),
)


def create_fixture(root):
    """Record synthetic-only approval metadata inside a temporary test fixture."""
    corpus = root / "corpus"
    corpus.mkdir()
    policy = {
        "schema_version": 1, "policy_id": "synthetic-t06-policy", "revision": 1,
        "jurisdiction": "ES", "reference_date": EVALUATION_DATE,
        "review": {"status": "approved", "reviewer": "SYNTHETIC TEST FIXTURE ONLY",
                   "reviewed_on": EVALUATION_DATE, "record": "synthetic-test-not-professional-approval"},
        "sources": {"allowed": ["SYNTHETIC"], "constraints": {
            "SYNTHETIC": {"jurisdictions": ["ES"], "url_hosts": ["example.invalid"]}}},
    }
    entries = []
    for doc_id, title, text in DOCUMENTS:
        content = text.encode("utf-8")
        filename = f"{doc_id}.txt"
        (corpus / filename).write_bytes(content)
        provenance = {
            "doc_id": doc_id, "source": "SYNTHETIC", "jurisdiction": "ES",
            "title": title, "family": "SYNTHETIC", "ref_url": f"https://example.invalid/{doc_id}",
            "version": "synthetic-v1", "version_date": EVALUATION_DATE, "language": "es",
            "retrieved_on": EVALUATION_DATE, "content_kind": "normative_text",
            "review": {"reviewer": "SYNTHETIC TEST FIXTURE ONLY", "reviewed_on": EVALUATION_DATE,
                       "record": "synthetic-test-not-professional-approval"},
            "reuse": {"basis": "Fictional software-test text; not an actual legal source",
                      "record": "synthetic-test-only"},
        }
        entries.append({"path": filename, "sha256": digest(content), "state": "admitted",
                        "reason": "Synthetic fixture only; no real source approved", "provenance": provenance})
    registry = {"schema_version": 1, "registry_id": "synthetic-t06-registry",
                "revision": 1, "documents": entries}
    registry_path = root / "registry.json"
    registry_path.write_bytes(canonical_json(registry))
    return corpus, registry_path, policy


def lexical_scan(records, query, k, policy):
    """Independent reference for the former regex/set-intersection scan.

    Sorting is stable and policy filtering happens before taking k. These
    fixtures have one distinct chunk per document, so no deduplication differs.
    """
    query_tokens = set(re.findall(r"\w+", query.lower(), re.U))
    scored = []
    for record in records:
        citation = citation_from_record(record)
        if citation is None or not source_is_allowed(policy, citation["meta"]):
            continue
        score = len(query_tokens & set(re.findall(r"\w+", citation["text"].lower(), re.U)))
        if score > 0:
            scored.append((score, citation))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [citation for _score, citation in scored[:k]]


def build_report():
    with tempfile.TemporaryDirectory(prefix="lexdomus-t06-evaluation-") as temporary, ExitStack() as stack:
        guards = []
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "llm.provider.call_llm_json"):
            guard = Mock(side_effect=AssertionError("Network and model requests forbidden"))
            stack.enter_context(patch(target, guard))
            guards.append(guard)
        root = Path(temporary)
        corpus, registry_path, policy = create_fixture(root)
        chunks, manifest = build_bundle(registry_path, corpus, policy)
        candidate = save_candidate(root / "candidates", chunks, manifest)
        prepared = prepare_snapshot(candidate, root / "prepared", policy, registry_path, corpus_dir=corpus)
        descriptor = json.loads((prepared / "snapshot.json").read_bytes())
        stack.enter_context(patch("lex_domus.snapshots.REGISTRY_PATH", registry_path))
        stack.enter_context(patch.dict("os.environ", {"LEXDOMUS_SNAPSHOT_DIR": str(prepared),
                                                      "LEXDOMUS_SNAPSHOT_ID": descriptor["snapshot_id"]}))
        snapshot = load_active_snapshot(policy)
        records = [json.loads(line) for line in chunks.splitlines()]
        rows = []
        for query_id, case_type, query, expected in QUERIES:
            actual = snapshot.search(query, TOP_K, policy)
            old = lexical_scan(records, query, TOP_K, policy)
            top_ids = [citation["meta"]["doc_id"] for citation in actual]
            hit = bool(set(expected) & set(top_ids)) if expected else not top_ids
            rows.append({"id": query_id, "case_type": case_type, "query": query,
                         "expected_doc_ids": list(expected), "top_doc_ids": top_ids,
                         "hit": hit, "all_expected_retrieved": set(expected) <= set(top_ids),
                         "reference_scan_doc_ids": [citation["meta"]["doc_id"] for citation in old],
                         "reference_scan_citations_equal": actual == old})
        for guard in guards:
            guard.assert_not_called()
        nonempty = [row for row in rows if row["expected_doc_ids"]]
        return {
            "schema_version": 1, "evaluation_date": EVALUATION_DATE, "base_commit": BASE_COMMIT,
            "scope": "Casos totalmente sintéticos: comprobación mecánica, no evaluación jurídica ni del despacho.",
            "method": {"pipeline": ["build_bundle", "prepare_snapshot", "load_active_snapshot", "search"],
                       "top_k": TOP_K, "hit_definition": "Con referencias: al menos un doc_id esperado entre los recuperados. Sin referencias: ninguna recuperación.",
                       "reference_scan": "Regex Unicode \\w+, minúsculas, conjuntos de tokens, puntuación por intersección, filtro de política antes de k y orden estable.",
                       "parity_scope": "Cinco documentos distintos de un fragmento; no evalúa diferencias intencionales de deduplicación.",
                       "network_requests": 0, "model_requests": 0},
            "retrieval_context": snapshot.context(),
            "documents": [{"doc_id": doc_id, "title": title, "text": text} for doc_id, title, text in DOCUMENTS],
            "queries": rows,
            "summary": {"document_count": len(DOCUMENTS), "chunk_count": len(records),
                        "query_count": len(rows), "queries_with_expected_documents": len(nonempty),
                        "hits_with_expected_documents": sum(row["hit"] for row in nonempty),
                        "empty_reference_cases": len(rows) - len(nonempty),
                        "correct_empty_results": sum(row["hit"] for row in rows if not row["expected_doc_ids"]),
                        "hits_including_empty_reference_cases": sum(row["hit"] for row in rows),
                        "reference_scan_parity_count": sum(row["reference_scan_citations_equal"] for row in rows),
                        "all_reference_scan_results_equal": all(row["reference_scan_citations_equal"] for row in rows),
                        "missed_query_ids": [row["id"] for row in rows if not row["hit"]]},
            "limitations": [
                "Q07 espera el documento sobre plazo pero usa sinónimos sin coincidencias léxicas; ambos recuperadores devuelven cero resultados.",
                "Ocho consultas fijadas sobre cinco textos ficticios no estiman precisión, exhaustividad ni suficiencia jurídica en casos reales.",
                "Los metadatos de aprobación existen exclusivamente en una fixture temporal de software; no representan aprobación de fuentes reales ni del despacho.",
                "No se comparan modelos semánticos ni rendimiento; ningún índice persistente participa.",
            ],
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path, help="Write the reproducible JSON report")
    output.add_argument("--check", action="store_true", help="Compare with the committed JSON evidence")
    args = parser.parse_args(argv)
    encoded = (json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        try:
            matches = EVIDENCE_PATH.read_bytes() == encoded
        except OSError:
            matches = False
        if not matches:
            print("Synthetic retrieval evidence differs; inspect the results before updating it.", file=sys.stderr)
            return 1
        print("Synthetic retrieval evidence reproduced exactly; known synonym miss retained.")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    else:
        sys.stdout.write(encoded.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
