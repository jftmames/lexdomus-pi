"""
agents/deliberative/evidence_assembler.py — Evidence Assembler

Executes retrieval plans and builds "evidence packs" with traceable citations.
claims[] are micro-assertions not yet drafted as clause text.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Set

from agents.base import BaseAgent
from agents.contracts import (
    Claim,
    EvidenceAssemblerInput,
    EvidenceAssemblerOutput,
    EvidencePack,
    Jurisdiction,
    RetrievalPlan,
    RetrievalQuery,
    SupportingSource,
)

logger = logging.getLogger("lexdomus.agents.evidence_assembler")

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "docs_chunks" / "chunks.jsonl"

_WORD = re.compile(r"\w+", re.U)


def _tok(s: str) -> Set[str]:
    return set(_WORD.findall((s or "").lower()))


def _retrieve_from_chunks(query: RetrievalQuery, k: int = 6) -> List[Dict[str, Any]]:
    """Token-overlap retrieval from chunks.jsonl (reuses existing retriever logic)."""
    if not CHUNKS_PATH.exists():
        return []

    q_tokens = _tok(query.query_text)
    scored: List[Dict[str, Any]] = []

    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            meta = rec.get("meta", {})
            text = rec.get("text", "")

            # Apply jurisdiction filter
            if query.jurisdiction_filter:
                if meta.get("jurisdiction", "") != query.jurisdiction_filter.value:
                    continue

            # Apply deprecated filter (default: exclude deprecated)
            if not query.deprecated and meta.get("deprecated", False):
                continue

            score = len(q_tokens & _tok(text))
            if score > 0:
                scored.append({
                    "text": text,
                    "meta": meta,
                    "score": score,
                    "doc_id": rec.get("doc_id", ""),
                })

    scored.sort(key=lambda r: r.get("score", 0), reverse=True)
    return scored[:k]


def _to_supporting_source(rec: Dict[str, Any], relevance: float) -> SupportingSource:
    meta = rec.get("meta", {})
    return SupportingSource(
        chunk_id=rec.get("doc_id", ""),
        source_id=rec.get("doc_id", "").split("#")[0] if "#" in rec.get("doc_id", "") else rec.get("doc_id", ""),
        canonical_citation=meta.get("ref_label", ""),
        text_excerpt=rec.get("text", "")[:500],
        jurisdiction=Jurisdiction(meta.get("jurisdiction", "ES")),
        doc_type=meta.get("family", ""),
        pinpoint=bool(meta.get("pinpoint", False)),
        relevance_score=relevance,
    )


def _execute_plan(plan: RetrievalPlan) -> EvidencePack:
    """Execute all queries in a retrieval plan and assemble evidence."""
    all_supporting: List[SupportingSource] = []
    all_counter: List[SupportingSource] = []
    seen_chunks: Set[str] = set()

    for query in plan.queries:
        results = _retrieve_from_chunks(query, k=6)
        for i, rec in enumerate(results):
            chunk_id = rec.get("doc_id", "")
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            relevance = max(0.0, min(1.0, rec.get("score", 0) / 10.0))
            source = _to_supporting_source(rec, relevance)
            all_supporting.append(source)

    # Build claims from supporting sources
    claims: List[Claim] = []
    for i, src in enumerate(all_supporting):
        claims.append(
            Claim(
                claim_id=f"{plan.context_id}:CLM-{i+1:03d}",
                statement=f"Según {src.canonical_citation}: {src.text_excerpt[:200]}",
                supporting_sources=[src],
                confidence=src.relevance_score,
            )
        )

    # Calculate coverage: how many must_have refs were found
    found_refs = {s.canonical_citation for s in all_supporting if s.canonical_citation}
    must_have_count = len(plan.must_have)
    found_count = sum(
        1 for ref in plan.must_have
        if any(ref.lower() in r.lower() for r in found_refs)
    )
    coverage = found_count / must_have_count if must_have_count > 0 else (1.0 if all_supporting else 0.0)

    return EvidencePack(
        context_id=plan.context_id,
        claims=claims,
        supporting_sources=all_supporting,
        counter_sources=all_counter,
        coverage_ratio=coverage,
    )


class EvidenceAssemblerAgent(BaseAgent[EvidenceAssemblerInput, EvidenceAssemblerOutput]):
    @property
    def name(self) -> str:
        return "evidence-assembler"

    def execute(self, inp: EvidenceAssemblerInput) -> EvidenceAssemblerOutput:
        packs = [_execute_plan(plan) for plan in inp.plans]
        return EvidenceAssemblerOutput(evidence_packs=packs)
