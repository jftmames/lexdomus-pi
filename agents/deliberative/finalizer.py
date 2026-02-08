"""
agents/deliberative/finalizer.py — Finalizer (Paso 14)

Produces final artifact: PDF path + reasoning trace + hash/signature.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

from agents.base import BaseAgent
from agents.contracts import (
    DraftCitation,
    EEEReport,
    FinalArtifact,
    FinalizerInput,
)

logger = logging.getLogger("lexdomus.agents.finalizer")

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "outputs"


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_trace(
    text: str,
    citations: list[DraftCitation],
    eee: EEEReport,
    session_id: str,
) -> Dict[str, Any]:
    """Build a full reasoning trace for auditability."""
    return {
        "session_id": session_id,
        "timestamp": int(time.time()),
        "text_length": len(text),
        "citation_count": len(citations),
        "citations": [
            {
                "marker": c.marker,
                "canonical": c.canonical,
                "chunk_id": c.chunk_id,
            }
            for c in citations
        ],
        "eee_scores": {
            "T": eee.score_T,
            "J": eee.score_J,
            "P": eee.score_P,
            "total": eee.score_total,
        },
        "gate_status": eee.gate_status.value,
        "gaps": [
            {"type": g.gap_type, "description": g.description, "severity": g.severity}
            for g in eee.missing_gaps
        ],
    }


class FinalizerAgent(BaseAgent[FinalizerInput, FinalArtifact]):
    @property
    def name(self) -> str:
        return "finalizer"

    def execute(self, inp: FinalizerInput) -> FinalArtifact:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Build trace
        trace = _build_trace(inp.text, inp.citations, inp.eee_report, inp.session_id)

        # Compute content hash
        content_hash = _compute_hash(inp.text)

        # Build signature (hash of trace + content)
        signature_payload = json.dumps({
            "content_hash": content_hash,
            "trace_hash": _compute_hash(json.dumps(trace, sort_keys=True)),
            "session_id": inp.session_id,
            "timestamp": trace["timestamp"],
        }, sort_keys=True)
        signature = _compute_hash(signature_payload)

        # Save trace JSON
        trace_path = OUTPUT_DIR / f"{inp.session_id}_trace.json"
        trace_path.write_text(
            json.dumps(trace, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Save plain text output (PDF generation deferred to a render step)
        text_path = OUTPUT_DIR / f"{inp.session_id}_output.md"
        text_path.write_text(inp.text, encoding="utf-8")

        logger.info(
            "Finalized session=%s hash=%s signature=%s",
            inp.session_id,
            content_hash[:12],
            signature[:12],
        )

        return FinalArtifact(
            pdf_path=str(text_path),  # markdown for now; PDF render is a separate step
            pdf_hash=content_hash,
            signature=signature,
            trace=trace,
            eee_summary={
                "T": inp.eee_report.score_T,
                "J": inp.eee_report.score_J,
                "P": inp.eee_report.score_P,
                "total": inp.eee_report.score_total,
            },
        )
