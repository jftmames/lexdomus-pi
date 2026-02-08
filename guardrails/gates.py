"""
guardrails/gates.py — Human gates for controlled externalization of judgment.

5.2 Gates humanos:
  - Before finalize: user sees evidence, gaps, conflicts.
  - If Repair Agent can't find support: re-inquire, don't invent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from agents.contracts import (
    ContradictionCheckerOutput,
    DraftingAgentOutput,
    EEEReport,
    EvidencePack,
    GateStatus,
)

logger = logging.getLogger("lexdomus.guardrails.gates")


@dataclass
class HumanReviewPackage:
    """
    Everything the user needs to see before finalize.
    Corresponds to the "Research Workbench" UX.
    """
    # Evidence panel
    evidence_summary: List[dict] = field(default_factory=list)
    # Gaps panel
    gaps: List[dict] = field(default_factory=list)
    # Conflicts panel
    conflicts: List[dict] = field(default_factory=list)
    # Draft panel
    draft_text: str = ""
    draft_citations: List[dict] = field(default_factory=list)
    # EEE panel
    eee_scores: dict = field(default_factory=dict)
    # Decision required
    gate_status: str = "NEEDS_HUMAN"
    human_question: str = ""


class HumanGate:
    """
    Builds a review package for the user before finalization.

    The user can:
      - Approve -> proceed to finalize
      - Request improvement -> re-run repair
      - Provide additional context -> feed back to evidence assembler
    """

    def build_review(
        self,
        draft: DraftingAgentOutput,
        eee_report: EEEReport,
        evidence_packs: List[EvidencePack],
        conflicts: Optional[ContradictionCheckerOutput] = None,
        human_question: str = "",
    ) -> HumanReviewPackage:
        """Build the review package for the user."""

        # Evidence summary
        evidence_summary = []
        for pack in evidence_packs:
            for src in pack.supporting_sources:
                evidence_summary.append({
                    "chunk_id": src.chunk_id,
                    "citation": src.canonical_citation,
                    "jurisdiction": src.jurisdiction.value,
                    "pinpoint": src.pinpoint,
                    "excerpt": src.text_excerpt[:200],
                    "relevance": src.relevance_score,
                })

        # Gaps
        gaps = [
            {
                "type": g.gap_type,
                "description": g.description,
                "severity": g.severity,
                "section": g.affected_section,
            }
            for g in eee_report.missing_gaps
        ]

        # Conflicts
        conflict_list = []
        if conflicts:
            for c in conflicts.conflicts:
                conflict_list.append({
                    "type": c.conflict_type.value,
                    "description": c.description,
                    "sources": c.involved_sources[:5],
                    "resolution": c.required_resolution,
                })

        # Draft citations (collapsible in UX)
        draft_citations = [
            {
                "marker": c.marker,
                "canonical": c.canonical,
                "excerpt": c.text_excerpt[:150],
            }
            for c in draft.citations
        ]

        return HumanReviewPackage(
            evidence_summary=evidence_summary,
            gaps=gaps,
            conflicts=conflict_list,
            draft_text=draft.text,
            draft_citations=draft_citations,
            eee_scores={
                "T": eee_report.score_T,
                "J": eee_report.score_J,
                "P": eee_report.score_P,
                "total": eee_report.score_total,
                "gate": eee_report.gate_status.value,
            },
            gate_status=eee_report.gate_status.value,
            human_question=human_question,
        )
