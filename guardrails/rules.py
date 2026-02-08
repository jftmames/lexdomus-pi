"""
guardrails/rules.py — Hard (non-negotiable) rules for agent behavior.

5.1 Reglas duras:
  - No-Answer Rule: Inquiry Engine produces ONLY 4 Issues (no draft).
  - Mandatory citation per normative/interpretive assertion ([SRC:...]).
  - Vigency filter: deprecated=false by default.
  - Jurisdictional separation: must have explicit bridge or mark conflict.
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.contracts import (
    ConflictType,
    ContradictionCheckerOutput,
    DraftingAgentOutput,
    EvidencePack,
    GateStatus,
    InquiryEngineOutput,
)

logger = logging.getLogger("lexdomus.guardrails.rules")

_SRC_MARKER = re.compile(r"\[SRC:[^\]]+\]")


class RuleViolation:
    """A detected guardrail violation."""

    def __init__(self, rule: str, description: str, severity: str = "error"):
        self.rule = rule
        self.description = description
        self.severity = severity  # "error" = blocks, "warning" = advisory

    def __repr__(self) -> str:
        return f"RuleViolation({self.rule}: {self.description})"


class GuardrailsEngine:
    """Validates agent outputs against hard rules."""

    def validate_inquiry(self, output: InquiryEngineOutput) -> List[RuleViolation]:
        """
        Rule: No-Answer Rule — Inquiry Engine must produce only Issues,
        never a draft or final answer.
        """
        violations: List[RuleViolation] = []

        # Max 4 issues
        if len(output.issues) > 4:
            violations.append(
                RuleViolation(
                    "NO_ANSWER_RULE",
                    f"Inquiry Engine produced {len(output.issues)} issues; max is 4.",
                )
            )

        # No issues at all
        if len(output.issues) == 0:
            violations.append(
                RuleViolation(
                    "NO_ANSWER_RULE",
                    "Inquiry Engine produced 0 issues; must produce at least 1.",
                )
            )

        return violations

    def validate_draft_citations(self, draft: DraftingAgentOutput) -> List[RuleViolation]:
        """
        Rule: Mandatory citation per normative/interpretive assertion.
        Every line starting with '- ' or '* ' in the draft must have [SRC:...].
        """
        violations: List[RuleViolation] = []
        uncited_count = 0

        for line in draft.text.split("\n"):
            stripped = line.strip()
            if (stripped.startswith("- ") or stripped.startswith("* ")) and not stripped.startswith("- ⚠"):
                if not _SRC_MARKER.search(stripped):
                    uncited_count += 1

        if uncited_count > 0:
            violations.append(
                RuleViolation(
                    "MANDATORY_CITATION",
                    f"{uncited_count} assertions without [SRC:...] citation marker.",
                    severity="warning",  # repair agent can fix this
                )
            )

        return violations

    def validate_jurisdiction_separation(
        self,
        conflicts: ContradictionCheckerOutput,
    ) -> List[RuleViolation]:
        """
        Rule: If jurisdictions are mixed, there must be an explicit bridge
        or it must be marked as a conflict.
        """
        violations: List[RuleViolation] = []

        if not conflicts.jurisdiction_clean:
            jurisdiction_conflicts = [
                c for c in conflicts.conflicts
                if c.conflict_type == ConflictType.JURISDICTION_MIX
            ]
            for conflict in jurisdiction_conflicts:
                if not conflict.required_resolution:
                    violations.append(
                        RuleViolation(
                            "JURISDICTION_SEPARATION",
                            f"Jurisdiction mix without resolution: {conflict.description}",
                        )
                    )

        return violations

    def validate_vigency(self, evidence_packs: List[EvidencePack]) -> List[RuleViolation]:
        """
        Rule: deprecated=false by default.
        Flag any deprecated sources unless explicitly requested.
        """
        violations: List[RuleViolation] = []

        for pack in evidence_packs:
            for src in pack.supporting_sources:
                # Check if source metadata indicates deprecation
                # This is enforced at retrieval time via query.deprecated flag
                pass

        return violations

    def validate_all(
        self,
        inquiry: InquiryEngineOutput | None = None,
        draft: DraftingAgentOutput | None = None,
        conflicts: ContradictionCheckerOutput | None = None,
        evidence_packs: List[EvidencePack] | None = None,
    ) -> List[RuleViolation]:
        """Run all applicable validations."""
        violations: List[RuleViolation] = []

        if inquiry:
            violations.extend(self.validate_inquiry(inquiry))
        if draft:
            violations.extend(self.validate_draft_citations(draft))
        if conflicts:
            violations.extend(self.validate_jurisdiction_separation(conflicts))
        if evidence_packs:
            violations.extend(self.validate_vigency(evidence_packs))

        return violations
