"""
agents/deliberative/retrieval_planner.py — Retrieval Planner

Given issues from Inquiry Engine, decides what to search:
normativa aplicable + jurisprudencia relevante + doctrina de apoyo.
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    Issue,
    Jurisdiction,
    RetrievalPlan,
    RetrievalPlannerInput,
    RetrievalPlannerOutput,
    RetrievalQuery,
    SignalType,
)

logger = logging.getLogger("lexdomus.agents.retrieval_planner")

# Map encaje_ref patterns to query types
_REF_TO_QUERY_TYPES = {
    "normativa": [
        re.compile(r"\b(?:LPI|TRLPI|USC|Directiva|GDPR|RGPD|Berna|Berne)\b", re.I),
    ],
    "jurisprudencia": [
        re.compile(r"\b(?:STS|STJUE|CJEU|sentencia)\b", re.I),
    ],
    "doctrina": [
        re.compile(r"\b(?:doctrina|comentario|manual)\b", re.I),
    ],
}


def _extract_must_have(issue: Issue) -> List[str]:
    """Extract canonical citation references that must appear in results."""
    refs = []
    if issue.encaje_ref:
        # Split multiple references
        parts = re.split(r"[;,]", issue.encaje_ref)
        refs.extend(p.strip() for p in parts if p.strip())
    return refs


def _plan_for_issue(issue: Issue, jurisdiction: Jurisdiction) -> RetrievalPlan:
    """Build a retrieval plan for a single issue."""
    queries: List[RetrievalQuery] = []
    must_have = _extract_must_have(issue)

    # Query 1: normativa — always
    queries.append(
        RetrievalQuery(
            query_text=issue.pregunta,
            query_type="normativa",
            jurisdiction_filter=jurisdiction,
            must_have_signals=[],
        )
    )

    # Query 2: if encaje_ref is given, search specifically for those articles
    if issue.encaje_ref:
        queries.append(
            RetrievalQuery(
                query_text=issue.encaje_ref,
                query_type="normativa",
                jurisdiction_filter=jurisdiction,
            )
        )

    # Query 3: jurisprudencia — use principio as additional context
    if issue.principio:
        queries.append(
            RetrievalQuery(
                query_text=f"{issue.pregunta} {issue.principio}",
                query_type="jurisprudencia",
                jurisdiction_filter=jurisdiction,
            )
        )

    # Query 4: search for exceptions/definitions if evidencias mention them
    for ev in issue.evidencias_requeridas:
        ev_lower = ev.lower()
        if any(kw in ev_lower for kw in ("excepción", "exception", "limitación")):
            queries.append(
                RetrievalQuery(
                    query_text=ev,
                    query_type="normativa",
                    jurisdiction_filter=jurisdiction,
                    must_have_signals=[SignalType.EXCEPTION],
                )
            )
        elif any(kw in ev_lower for kw in ("plazo", "duración", "deadline")):
            queries.append(
                RetrievalQuery(
                    query_text=ev,
                    query_type="normativa",
                    jurisdiction_filter=jurisdiction,
                    must_have_signals=[SignalType.DEADLINE],
                )
            )

    return RetrievalPlan(
        context_id=issue.issue_id,
        queries=queries,
        must_have=must_have,
    )


class RetrievalPlannerAgent(BaseAgent[RetrievalPlannerInput, RetrievalPlannerOutput]):
    @property
    def name(self) -> str:
        return "retrieval-planner"

    def execute(self, inp: RetrievalPlannerInput) -> RetrievalPlannerOutput:
        plans = [
            _plan_for_issue(issue, inp.jurisdiction)
            for issue in inp.issues
        ]
        return RetrievalPlannerOutput(plans=plans)
