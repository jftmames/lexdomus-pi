"""Two fixed mechanical examples. Never accepts real clauses or calls an LLM."""
from functools import lru_cache
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.main import analyze, error_response, invalid_request
from api.schemas import AnalyzeIn
from app.pipeline import analyze_clause
from lex_domus.ingestion import build_bundle, canonical_json, digest, save_candidate
from lex_domus.snapshots import load_snapshot, prepare_snapshot

EXAMPLES = ("zafiroqwerty", "inexistenteqwerty")
SOURCE = b"zafiroqwerty\n"
POLICY = {
    "schema_version": 1, "policy_id": "synthetic-vercel-demo-only", "revision": 1,
    "jurisdiction": "ES", "reference_date": "2026-09-09",
    "review": {"status": "approved", "reviewer": "SYNTHETIC DEMO ONLY",
               "reviewed_on": "2026-09-09", "record": "fictional-mechanical-test-not-legal-approval"},
    "sources": {"allowed": ["SYNTHETIC"], "constraints": {
        "SYNTHETIC": {"jurisdictions": ["ES"], "url_hosts": ["example.invalid"]}}},
}


@lru_cache(maxsize=1)
def synthetic_snapshot():
    # A unique temporary directory per initialization; never write into the repo.
    # Only the verified, immutable in-memory snapshot survives cleanup.
    with TemporaryDirectory(prefix="lexdomus-synthetic-") as directory:
        root = Path(directory)
        corpus = root / "corpus"
        corpus.mkdir()
        (corpus / "source.txt").write_bytes(SOURCE)
        provenance = {
            "doc_id": "synthetic-demo", "source": "SYNTHETIC", "jurisdiction": "ES",
            "title": "Ejemplo sintético sin valor jurídico", "family": "synthetic-only",
            "ref_url": "https://example.invalid/synthetic-demo", "version": "synthetic-v1",
            "version_date": "2026-09-09", "language": "es", "retrieved_on": "2026-09-09",
            "content_kind": "normative_text",
            "review": {"reviewer": "SYNTHETIC DEMO ONLY", "reviewed_on": "2026-09-09",
                       "record": "fictional-mechanical-test-only"},
            "reuse": {"basis": "Original synthetic token", "record": "synthetic-only"},
        }
        registry = root / "registry.json"
        registry.write_bytes(canonical_json({
            "schema_version": 1, "registry_id": "synthetic-demo-only", "revision": 1,
            "documents": [{"path": "source.txt", "sha256": digest(SOURCE), "state": "admitted",
                           "reason": "Synthetic token only", "provenance": provenance}],
        }))
        chunks, manifest = build_bundle(registry, corpus, POLICY)
        candidate = save_candidate(root / "candidates", chunks, manifest)
        snapshot = prepare_snapshot(candidate, root / "snapshots", POLICY, registry, corpus_dir=corpus)
        identifier = json.loads((snapshot / "snapshot.json").read_text())["snapshot_id"]
        return load_snapshot(POLICY, str(snapshot), identifier, registry)


def synthetic_writer(*_args):
    return {"analysis_md": "Prueba técnica: se ha recuperado el token del corpus sintético. "
                           "Este resultado no contiene una valoración jurídica.",
            "pros": [], "cons": [], "devils_advocate": {}}


def synthetic_analyze(clause, jurisdiction):
    if clause not in EXAMPLES:
        raise ValueError("Only fixed synthetic examples are accepted")
    result = analyze_clause(clause, jurisdiction, policy=POLICY, snapshot=synthetic_snapshot(),
                            writer=synthetic_writer, trace=False)
    # Heuristic alternatives and EEE are not legal or quality evidence for tokens.
    result.update(alternative_clause=None, EEE=None, flags=[])
    return result


app = FastAPI(title="LexDomus synthetic pilot", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware,
                   allow_origins=["https://lexdomus-pi-piloto.vercel.app"],
                   allow_methods=["POST", "GET"], allow_headers=["Content-Type"])
app.state.analyzer = synthetic_analyze
app.add_exception_handler(RequestValidationError, invalid_request)


@app.get("/health")
def health():
    return {"status": "ok", "synthetic_only": True, "llm_enabled": False,
            "examples": list(EXAMPLES), "retrieval_context": synthetic_snapshot().context()}


@app.post("/analyze")
def analyze_example(body: AnalyzeIn, request: Request):
    if body.clause not in EXAMPLES:
        return error_response(request, 422, "INVALID_INPUT", "Selecciona uno de los dos ejemplos sintéticos del piloto.")
    response = analyze(body, request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-LexDomus-Mode"] = "synthetic-only"
    return response
