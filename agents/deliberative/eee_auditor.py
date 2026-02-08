"""
agents/deliberative/eee_auditor.py — EEE Auditor (Paso 11)

Scores 0–100 on three epistemic dimensions:
  T (Trazabilidad/Traceability), J (Justificación), P (Pluralidad)
Lists gaps: "falta artículo", "cita débil", "conflicto jurisdiccional".
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    Conflict,
    DraftingAgentOutput,
    EEEAuditorInput,
    EEEGap,
    EEEReport,
    EvidencePack,
    GateStatus,
)

logger = logging.getLogger("lexdomus.agents.eee_auditor")

# Policy thresholds (can be overridden by policy.yaml)
DEFAULT_MIN_T = 70.0
DEFAULT_MIN_J = 60.0
DEFAULT_MIN_P = 60.0

_SRC_MARKER = re.compile(r"\[SRC:[^\]]+\]")


def _score_traceability(draft: DraftingAgentOutput, packs: List[EvidencePack]) -> tuple[float, List[EEEGap]]:
    """
    T: proportion of assertions with pinpoint citations.
    100 = every assertion anchored; 0 = no citations at all.
    """
    gaps: List[EEEGap] = []

    # Count assertions (lines starting with "- ")
    lines = draft.text.split("\n")
    assertion_lines = [l for l in lines if l.strip().startswith("- ") or l.strip().startswith("* ")]
    total_assertions = max(len(assertion_lines), 1)

    # Count cited assertions
    cited = sum(1 for l in assertion_lines if _SRC_MARKER.search(l))

    # Check pinpoint quality
    pinpoint_citations = sum(1 for c in draft.citations if c.canonical)
    total_citations = max(len(draft.citations), 1)
    pinpoint_ratio = pinpoint_citations / total_citations

    score = (cited / total_assertions) * 70 + pinpoint_ratio * 30

    if cited < total_assertions:
        gaps.append(
            EEEGap(
                gap_type="missing_citation",
                description=f"{total_assertions - cited} afirmaciones sin cita [SRC:...]",
                severity="high" if cited < total_assertions * 0.5 else "medium",
            )
        )

    if pinpoint_ratio < 0.8:
        gaps.append(
            EEEGap(
                gap_type="weak_citation",
                description=f"Solo {pinpoint_ratio:.0%} de las citas son pinpoint",
                severity="medium",
            )
        )

    return min(100.0, max(0.0, score)), gaps


def _score_justification(draft: DraftingAgentOutput, packs: List[EvidencePack]) -> tuple[float, List[EEEGap]]:
    """
    J: presence of rule→facts→application pattern + conflict handling.
    """
    gaps: List[EEEGap] = []
    score = 0.0

    # Check for rule (normative references)
    has_rule = bool(draft.citations)
    if has_rule:
        score += 30
    else:
        gaps.append(
            EEEGap(
                gap_type="missing_rule",
                description="No se citan normas aplicables",
                severity="high",
            )
        )

    # Check for facts (clause analysis)
    has_facts = "cláusula" in draft.text.lower() or "clause" in draft.text.lower()
    if has_facts:
        score += 20
    else:
        gaps.append(
            EEEGap(
                gap_type="missing_facts",
                description="No se analiza la cláusula/hechos concretos",
                severity="medium",
            )
        )

    # Check for application (conclusions / pros/cons)
    has_application = bool(draft.pros) or bool(draft.cons)
    if has_application:
        score += 30
    else:
        gaps.append(
            EEEGap(
                gap_type="missing_application",
                description="Faltan conclusiones (pros/contras)",
                severity="medium",
            )
        )

    # Bonus for conflict handling
    has_conflicts_addressed = any(
        "conflicto" in line.lower() or "tensión" in line.lower()
        for line in draft.text.split("\n")
    )
    if has_conflicts_addressed:
        score += 20

    return min(100.0, max(0.0, score)), gaps


def _score_plurality(draft: DraftingAgentOutput) -> tuple[float, List[EEEGap]]:
    """
    P: presence and quality of ≥1 reasonable alternative.
    """
    gaps: List[EEEGap] = []
    score = 0.0

    # Check devil's advocate
    da = draft.devils_advocate
    has_da = bool(da) and any(v and v != "-" for v in da.values())
    if has_da:
        score += 50
    else:
        gaps.append(
            EEEGap(
                gap_type="missing_plurality",
                description="Falta devil's advocate / lectura alternativa",
                severity="medium",
            )
        )

    # Check counter sources in evidence
    has_pros = bool(draft.pros)
    has_cons = bool(draft.cons)

    if has_pros and has_cons:
        score += 30
    elif has_pros or has_cons:
        score += 15
        gaps.append(
            EEEGap(
                gap_type="unbalanced_analysis",
                description="Análisis desbalanceado (solo pros o solo contras)",
                severity="low",
            )
        )

    # Bonus for multiple perspectives
    if len(draft.cons) >= 2:
        score += 20

    return min(100.0, max(0.0, score)), gaps


class EEEAuditorAgent(BaseAgent[EEEAuditorInput, EEEReport]):
    @property
    def name(self) -> str:
        return "eee-auditor"

    def execute(self, inp: EEEAuditorInput) -> EEEReport:
        all_gaps: List[EEEGap] = []

        score_t, gaps_t = _score_traceability(inp.draft, inp.evidence_packs)
        all_gaps.extend(gaps_t)

        score_j, gaps_j = _score_justification(inp.draft, inp.evidence_packs)
        all_gaps.extend(gaps_j)

        score_p, gaps_p = _score_plurality(inp.draft)
        all_gaps.extend(gaps_p)

        # Add conflict-related gaps
        for conflict in inp.conflicts:
            all_gaps.append(
                EEEGap(
                    gap_type="jurisdiction_conflict" if "jurisdicc" in conflict.description.lower() else "conflict",
                    description=conflict.description,
                    affected_section=conflict.required_resolution,
                    severity="high",
                )
            )

        total = (score_t + score_j + score_p) / 3.0

        # Determine gate status
        if score_t >= DEFAULT_MIN_T and score_j >= DEFAULT_MIN_J and score_p >= DEFAULT_MIN_P:
            gate = GateStatus.OK
        elif any(g.severity == "high" for g in all_gaps):
            gate = GateStatus.NO_CONCLUYENTE
        else:
            gate = GateStatus.NEEDS_HUMAN

        return EEEReport(
            score_T=round(score_t, 1),
            score_J=round(score_j, 1),
            score_P=round(score_p, 1),
            score_total=round(total, 1),
            missing_gaps=all_gaps,
            gate_status=gate,
        )
