# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from time import perf_counter
from pathlib import Path
from typing import Optional
import sys, os, logging

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("lexdomus.api")

# Legacy pipeline (backward compatible)
from app.pipeline import analyze_clause

# New agent topology
from agents.contracts import Jurisdiction, SessionState, GateStatus
from orchestration.workflow_engine import WorkflowEngine, WorkflowResult
from orchestration.session import SessionManager
from orchestration.state_store import StateStore
from orchestration.event_bus import EventBus
from guardrails.gates import HumanGate

# Opcional: MCP health si está presente
try:
    from mcp.registry import health as mcp_health, list_connectors
    HAS_MCP = True
except Exception:
    HAS_MCP = False

# --- Request/Response models ---

class AnalyzeIn(BaseModel):
    clause: str
    jurisdiction: str

class DeliberateIn(BaseModel):
    clause: str
    jurisdiction: str = "ES"
    instrument_type: str = "clausula"

class SessionResumeIn(BaseModel):
    session_id: str
    human_input: Optional[str] = None

# --- Shared infrastructure ---

_event_bus = EventBus()
_state_store = StateStore()
_session_mgr = SessionManager(store=_state_store)
_workflow = WorkflowEngine(event_bus=_event_bus, state_store=_state_store)
_human_gate = HumanGate()

app = FastAPI(title="LexDomus-PI API", version="2.0.0")

# CORS abierto para demos (restringe en prod con NEXT_PUBLIC_WEB_ORIGIN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "LexDomus API v2 — Agent Topology. Go to /docs for Swagger UI."}


@app.get("/health")
def health():
    data = {
        "status": "ok",
        "version": "2.0.0",
        "topology": {
            "research_plane": [
                "source-watcher", "ingest-normalizer", "ontology-tagger",
                "citation-resolver", "indexer",
            ],
            "deliberative_plane": [
                "inquiry-engine", "retrieval-planner", "evidence-assembler",
                "contradiction-checker", "drafting-agent", "eee-auditor",
                "repair-agent", "finalizer",
            ],
        },
        "has_mcp": HAS_MCP,
        "connectors": list_connectors() if HAS_MCP else {},
        "indices": {
            "chunks": (ROOT / "data" / "docs_chunks" / "chunks.jsonl").exists(),
            "faiss": (ROOT / "indices" / "faiss.index").exists(),
            "bm25": (ROOT / "indices" / "bm25.pkl").exists(),
        },
        "active_sessions": len(_session_mgr.list_sessions()),
    }
    if HAS_MCP:
        try:
            data["mcp_corpus"] = mcp_health("corpus")
        except Exception:
            pass
    return data


# --- Legacy endpoint (backward compatible) ---

@app.post("/analyze")
def analyze(body: AnalyzeIn):
    t0 = perf_counter()
    try:
        res = analyze_clause(body.clause, body.jurisdiction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    res["latency_ms"] = round((perf_counter() - t0) * 1000.0, 2)
    return res


# --- New agent topology endpoints ---

@app.post("/deliberate")
def deliberate(body: DeliberateIn):
    """
    Run the full deliberative workflow through the agent topology.

    Returns the session state with all intermediate results,
    or pauses at a human gate if the Repair Agent needs input.
    """
    t0 = perf_counter()
    try:
        jurisdiction = Jurisdiction(body.jurisdiction)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid jurisdiction: {body.jurisdiction}")

    # Create session
    state = _session_mgr.create(
        clause=body.clause,
        jurisdiction=jurisdiction,
        instrument_type=body.instrument_type,
    )

    # Run workflow
    result = _workflow.run(state)

    # Build response
    response = _build_deliberation_response(result)
    response["latency_ms"] = round((perf_counter() - t0) * 1000.0, 2)
    return response


@app.post("/deliberate/resume")
def deliberate_resume(body: SessionResumeIn):
    """Resume a paused session (after human gate)."""
    state = _session_mgr.get(body.session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {body.session_id}")

    t0 = perf_counter()
    result = _workflow.run(state)
    response = _build_deliberation_response(result)
    response["latency_ms"] = round((perf_counter() - t0) * 1000.0, 2)
    return response


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get full session state for inspection / UX panels."""
    state = _session_mgr.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return state.model_dump()


@app.get("/session/{session_id}/review")
def get_review(session_id: str):
    """
    Get the human review package (evidence, gaps, conflicts, draft, EEE).
    Used by the Research Workbench UX.
    """
    state = _session_mgr.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not state.draft_versions:
        raise HTTPException(status_code=400, detail="No draft available yet")

    draft = state.draft_versions[-1]
    eee = state.eee_reports[-1] if state.eee_reports else None
    packs = state.evidence_packs.evidence_packs if state.evidence_packs else []

    if not eee:
        raise HTTPException(status_code=400, detail="No EEE report available yet")

    review = _human_gate.build_review(
        draft=draft,
        eee_report=eee,
        evidence_packs=packs,
        conflicts=state.conflicts,
    )
    return {
        "session_id": session_id,
        "evidence": review.evidence_summary,
        "gaps": review.gaps,
        "conflicts": review.conflicts,
        "draft": review.draft_text,
        "citations": review.draft_citations,
        "eee": review.eee_scores,
        "gate_status": review.gate_status,
        "human_question": review.human_question,
    }


@app.get("/sessions")
def list_sessions():
    """List all active session IDs."""
    return {"sessions": _session_mgr.list_sessions()}


def _build_deliberation_response(result: WorkflowResult) -> dict:
    """Convert WorkflowResult to API response dict."""
    resp: dict = {
        "session_id": result.session_state.session_id if result.session_state else "",
        "current_step": result.current_step.value,
        "error": result.error,
    }

    if result.needs_human_input:
        resp["status"] = "NEEDS_HUMAN"
        resp["human_question"] = result.human_question
    elif result.error:
        resp["status"] = "ERROR"
    elif result.final_artifact:
        resp["status"] = "DONE"
        resp["artifact"] = {
            "pdf_hash": result.final_artifact.pdf_hash,
            "signature": result.final_artifact.signature,
            "eee_summary": result.final_artifact.eee_summary,
        }
    else:
        resp["status"] = "IN_PROGRESS"

    # Include key outputs if available
    state = result.session_state
    if state:
        if state.inquiry_output:
            resp["issues"] = [
                {
                    "id": iss.issue_id,
                    "pregunta": iss.pregunta,
                    "encaje_ref": iss.encaje_ref,
                }
                for iss in state.inquiry_output.issues
            ]
            resp["risk_flags"] = [
                {"type": rf.flag_type, "description": rf.description, "severity": rf.severity}
                for rf in state.inquiry_output.risk_flags
            ]
        if state.eee_reports:
            last_eee = state.eee_reports[-1]
            resp["eee"] = {
                "T": last_eee.score_T,
                "J": last_eee.score_J,
                "P": last_eee.score_P,
                "total": last_eee.score_total,
                "gate": last_eee.gate_status.value,
                "gaps_count": len(last_eee.missing_gaps),
            }
        if state.conflicts:
            resp["conflicts_count"] = len(state.conflicts.conflicts)
            resp["jurisdiction_clean"] = state.conflicts.jurisdiction_clean

    return resp
