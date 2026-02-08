"""
agents/deliberative/drafting_agent.py — Drafting Agent (Paso 7)

Drafts text using evidence_pack. Every normative/interpretive assertion
is anchored with [SRC:chunk_id].
"""
from __future__ import annotations

import logging
import os
import textwrap
from typing import Dict, List

from agents.base import BaseAgent
from agents.contracts import (
    Conflict,
    DraftCitation,
    DraftingAgentInput,
    DraftingAgentOutput,
    EvidencePack,
    SupportingSource,
)

logger = logging.getLogger("lexdomus.agents.drafting_agent")


def _build_citation(src: SupportingSource) -> DraftCitation:
    return DraftCitation(
        marker=f"[SRC:{src.chunk_id}]",
        chunk_id=src.chunk_id,
        canonical=src.canonical_citation,
        text_excerpt=src.text_excerpt[:300],
    )


def _draft_heuristic(
    packs: List[EvidencePack],
    conflicts: List[Conflict],
    clause: str,
    jurisdiction: str,
    instrument_type: str,
) -> DraftingAgentOutput:
    """
    Build a structured draft from evidence packs.
    Each claim is anchored with [SRC:chunk_id].
    """
    sections: List[str] = []
    all_citations: List[DraftCitation] = []
    pros: List[str] = []
    cons: List[str] = []

    sections.append(f"**Cláusula analizada (jurisdicción: {jurisdiction})**\n\n{clause}")

    for pack in packs:
        sections.append(f"\n**Análisis — {pack.context_id}** (cobertura: {pack.coverage_ratio:.0%})")

        for claim in pack.claims:
            # Anchor each claim with its sources
            src_markers = []
            for src in claim.supporting_sources:
                citation = _build_citation(src)
                all_citations.append(citation)
                src_markers.append(citation.marker)

            marker_str = " ".join(src_markers) if src_markers else "[sin fuente]"
            sections.append(f"- {claim.statement} {marker_str}")

            if claim.confidence >= 0.5:
                pros.append(claim.statement[:200])
            else:
                cons.append(f"Evidencia débil: {claim.statement[:200]}")

        # Add counter-evidence
        for src in pack.counter_sources:
            citation = _build_citation(src)
            all_citations.append(citation)
            cons.append(f"Contra: {src.text_excerpt[:200]} {citation.marker}")

    # Add conflict warnings
    if conflicts:
        sections.append("\n**Conflictos detectados**")
        for conflict in conflicts:
            sections.append(f"- ⚠ {conflict.conflict_type.value}: {conflict.description}")
            cons.append(f"Conflicto: {conflict.description[:200]}")

    # Devils advocate
    devils_advocate: Dict[str, str] = {
        "hipotesis": "El cesionario necesita flexibilidad operativa razonable.",
        "lectura": "La cláusula podría interpretarse como una licencia amplia pero no como cesión plena.",
        "cuando_mejor": "Cuando se establecen límites claros y se preserva la paternidad del autor.",
    }

    if not pros:
        pros.append("Base para negociación dentro del marco legal aplicable.")
    if not cons:
        cons.append("Revisar concreción de modalidades, territorio y plazo.")

    text = "\n".join(sections)

    return DraftingAgentOutput(
        text=text,
        citations=all_citations,
        pros=pros[:5],
        cons=cons[:5],
        devils_advocate=devils_advocate,
    )


def _draft_llm(
    packs: List[EvidencePack],
    conflicts: List[Conflict],
    clause: str,
    jurisdiction: str,
    instrument_type: str,
) -> DraftingAgentOutput:
    """LLM-powered drafting (wraps existing writer_llm)."""
    try:
        from app.writer_llm import draft_opinion_llm

        # Convert packs to per_node format for backward compat
        per_node = []
        for pack in packs:
            citations = []
            for src in pack.supporting_sources:
                citations.append({
                    "text": src.text_excerpt,
                    "meta": {
                        "source": src.source_id,
                        "jurisdiction": src.jurisdiction.value,
                        "ref_label": src.canonical_citation,
                        "pinpoint": src.pinpoint,
                    },
                })
            per_node.append({
                "node": {"question": pack.context_id},
                "retrieval": {"status": "OK" if citations else "NO_EVIDENCE", "citations": citations},
            })

        flags = [c.description for c in conflicts]
        result = draft_opinion_llm(clause, jurisdiction, per_node, flags)

        # Convert to typed output
        all_citations = []
        for pack in packs:
            for src in pack.supporting_sources:
                all_citations.append(_build_citation(src))

        return DraftingAgentOutput(
            text=result.get("analysis_md", ""),
            citations=all_citations,
            pros=result.get("pros", []),
            cons=result.get("cons", []),
            devils_advocate=result.get("devils_advocate", {}),
        )
    except Exception:
        return _draft_heuristic(packs, conflicts, clause, jurisdiction, instrument_type)


class DraftingAgent(BaseAgent[DraftingAgentInput, DraftingAgentOutput]):
    @property
    def name(self) -> str:
        return "drafting-agent"

    def execute(self, inp: DraftingAgentInput) -> DraftingAgentOutput:
        use_llm = os.getenv("USE_LLM", "0") == "1"

        if use_llm:
            return _draft_llm(
                inp.evidence_packs,
                inp.conflicts,
                inp.clause,
                inp.jurisdiction.value,
                inp.instrument_type,
            )

        return _draft_heuristic(
            inp.evidence_packs,
            inp.conflicts,
            inp.clause,
            inp.jurisdiction.value,
            inp.instrument_type,
        )
