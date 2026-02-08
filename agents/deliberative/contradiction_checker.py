"""
agents/deliberative/contradiction_checker.py — Contradiction / Jurisdiction Checker

Detects jurisdiction mixing (ES/EU/US) without explicit bridge,
temporal conflicts, hierarchy conflicts, and internal tensions.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import List, Set

from agents.base import BaseAgent
from agents.contracts import (
    Conflict,
    ConflictType,
    ContradictionCheckerInput,
    ContradictionCheckerOutput,
    EvidencePack,
    Jurisdiction,
    SupportingSource,
)

logger = logging.getLogger("lexdomus.agents.contradiction_checker")

# Hierarchy: ley > reglamento > doctrina
_HIERARCHY = {
    "ley": 3,
    "reglamento": 2,
    "sentencia": 2,
    "doctrina": 1,
    "otro": 0,
}


def _check_jurisdiction_mix(
    packs: List[EvidencePack],
    target_jurisdiction: Jurisdiction,
) -> List[Conflict]:
    """Detect if evidence mixes jurisdictions without an explicit bridge."""
    conflicts: List[Conflict] = []
    all_jurisdictions: Set[str] = set()
    involved_sources: List[str] = []

    for pack in packs:
        for src in pack.supporting_sources:
            all_jurisdictions.add(src.jurisdiction.value)
            if src.jurisdiction != target_jurisdiction:
                involved_sources.append(src.canonical_citation)

    # If more than one jurisdiction appears, check for bridge
    if len(all_jurisdictions) > 1:
        conflicts.append(
            Conflict(
                conflict_type=ConflictType.JURISDICTION_MIX,
                description=(
                    f"Mezcla de jurisdicciones detectada: {', '.join(sorted(all_jurisdictions))}. "
                    f"Jurisdicción objetivo: {target_jurisdiction.value}. "
                    "Se requiere puente jurisdiccional explícito o separación de análisis."
                ),
                involved_sources=involved_sources[:10],
                required_resolution="Añadir puente jurisdiccional o marcar como análisis comparado",
            )
        )

    return conflicts


def _check_hierarchy_conflicts(packs: List[EvidencePack]) -> List[Conflict]:
    """Detect when lower-hierarchy sources contradict higher ones."""
    conflicts: List[Conflict] = []

    for pack in packs:
        # Group claims by doc_type hierarchy
        supporting_hierarchy: List[tuple] = []
        counter_hierarchy: List[tuple] = []

        for src in pack.supporting_sources:
            level = _HIERARCHY.get(src.doc_type, 0)
            supporting_hierarchy.append((level, src))

        for src in pack.counter_sources:
            level = _HIERARCHY.get(src.doc_type, 0)
            counter_hierarchy.append((level, src))

        # If a counter source has higher hierarchy than supporting
        if supporting_hierarchy and counter_hierarchy:
            max_support = max(h for h, _ in supporting_hierarchy)
            max_counter = max(h for h, _ in counter_hierarchy)
            if max_counter > max_support:
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.HIERARCHY_CONFLICT,
                        description=(
                            f"Fuente contraria de rango superior detectada en {pack.context_id}. "
                            "La norma de mayor jerarquía contradice la posición sostenida."
                        ),
                        involved_sources=[
                            s.canonical_citation for _, s in counter_hierarchy
                        ],
                        required_resolution="Revisar jerarquía normativa y ajustar conclusión",
                    )
                )

    return conflicts


def _check_internal_tensions(packs: List[EvidencePack]) -> List[Conflict]:
    """Detect internal tensions (e.g. general rule vs exception in same evidence)."""
    conflicts: List[Conflict] = []

    for pack in packs:
        # Detect if both supporting and counter sources exist
        if pack.supporting_sources and pack.counter_sources:
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.INTERNAL_TENSION,
                    description=(
                        f"Tensión interna en {pack.context_id}: "
                        f"{len(pack.supporting_sources)} fuentes a favor vs "
                        f"{len(pack.counter_sources)} fuentes en contra."
                    ),
                    involved_sources=[
                        s.canonical_citation
                        for s in pack.counter_sources[:5]
                    ],
                    required_resolution="Resolver tensión mediante interpretación jerárquica o temporal",
                )
            )

    return conflicts


class ContradictionCheckerAgent(BaseAgent[ContradictionCheckerInput, ContradictionCheckerOutput]):
    @property
    def name(self) -> str:
        return "contradiction-checker"

    def execute(self, inp: ContradictionCheckerInput) -> ContradictionCheckerOutput:
        all_conflicts: List[Conflict] = []

        # Check jurisdiction mixing
        all_conflicts.extend(
            _check_jurisdiction_mix(inp.evidence_packs, inp.jurisdiction)
        )

        # Check hierarchy conflicts
        all_conflicts.extend(
            _check_hierarchy_conflicts(inp.evidence_packs)
        )

        # Check internal tensions
        all_conflicts.extend(
            _check_internal_tensions(inp.evidence_packs)
        )

        jurisdiction_clean = not any(
            c.conflict_type == ConflictType.JURISDICTION_MIX
            for c in all_conflicts
        )

        return ContradictionCheckerOutput(
            conflicts=all_conflicts,
            jurisdiction_clean=jurisdiction_clean,
        )
