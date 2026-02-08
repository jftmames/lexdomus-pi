"""
agents/deliberative/repair_agent.py — Repair Agent (Pasos 12–13)

Rewrites and inserts missing citations. If the gap is epistemic
(not documental), requests a human question instead of inventing.
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    DraftChange,
    DraftCitation,
    DraftingAgentOutput,
    EEEGap,
    EEEReport,
    EvidencePack,
    GateStatus,
    RepairAgentInput,
    RepairAgentOutput,
    SupportingSource,
)

logger = logging.getLogger("lexdomus.agents.repair_agent")

_SRC_MARKER = re.compile(r"\[SRC:[^\]]+\]")


def _find_uncited_assertions(text: str) -> List[str]:
    """Find assertion lines without [SRC:...] markers."""
    uncited = []
    for line in text.split("\n"):
        stripped = line.strip()
        if (stripped.startswith("- ") or stripped.startswith("* ")) and not _SRC_MARKER.search(stripped):
            uncited.append(stripped)
    return uncited


def _find_best_source(
    assertion: str,
    packs: List[EvidencePack],
    used_chunks: set,
) -> SupportingSource | None:
    """Try to find a source that matches an uncited assertion."""
    assertion_lower = assertion.lower()
    best: SupportingSource | None = None
    best_overlap = 0

    for pack in packs:
        for src in pack.supporting_sources:
            if src.chunk_id in used_chunks:
                continue
            # Simple token overlap
            src_tokens = set(re.findall(r"\w+", src.text_excerpt.lower()))
            assert_tokens = set(re.findall(r"\w+", assertion_lower))
            overlap = len(src_tokens & assert_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best = src

    return best if best_overlap > 2 else None


class RepairAgent(BaseAgent[RepairAgentInput, RepairAgentOutput]):
    @property
    def name(self) -> str:
        return "repair-agent"

    def execute(self, inp: RepairAgentInput) -> RepairAgentOutput:
        changes: List[DraftChange] = []
        new_citations: List[DraftCitation] = []
        repaired_text = inp.draft.text
        needs_human = False
        human_question = ""

        # Track which chunks are already cited
        used_chunks = {c.chunk_id for c in inp.draft.citations}

        # Classify gaps
        documental_gaps = [g for g in inp.eee_report.missing_gaps if g.gap_type in (
            "missing_citation", "weak_citation", "missing_rule",
        )]
        epistemic_gaps = [g for g in inp.eee_report.missing_gaps if g.gap_type in (
            "missing_facts", "missing_application", "missing_plurality",
        )]

        # --- Repair documental gaps: try to insert citations ---
        uncited = _find_uncited_assertions(repaired_text)
        for assertion in uncited:
            best_src = _find_best_source(assertion, inp.evidence_packs, used_chunks)
            if best_src:
                marker = f"[SRC:{best_src.chunk_id}]"
                new_line = f"{assertion} {marker}"
                repaired_text = repaired_text.replace(assertion, new_line, 1)
                used_chunks.add(best_src.chunk_id)

                new_citations.append(
                    DraftCitation(
                        marker=marker,
                        chunk_id=best_src.chunk_id,
                        canonical=best_src.canonical_citation,
                        text_excerpt=best_src.text_excerpt[:300],
                    )
                )
                changes.append(
                    DraftChange(
                        change_type="insert_citation",
                        description=f"Añadida cita {marker} a: {assertion[:80]}...",
                        old_text=assertion,
                        new_text=new_line,
                    )
                )

        # --- Handle epistemic gaps: request human input ---
        unresolvable = []
        for gap in epistemic_gaps:
            if gap.severity == "high":
                unresolvable.append(gap.description)

        for gap in documental_gaps:
            # If we couldn't find sources for the gap, it's epistemic
            if gap.gap_type == "missing_rule" and not any(
                c.change_type == "insert_citation" for c in changes
            ):
                unresolvable.append(gap.description)

        if unresolvable:
            needs_human = True
            human_question = (
                "No se encontró sustento documental suficiente para: "
                + "; ".join(unresolvable[:3])
                + ". ¿Puede proporcionar contexto adicional o confirmar la interpretación?"
            )

        return RepairAgentOutput(
            text=repaired_text,
            changes=changes,
            new_citations=new_citations,
            needs_human_input=needs_human,
            human_question=human_question,
        )
