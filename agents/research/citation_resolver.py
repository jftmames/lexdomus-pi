"""
agents/research/citation_resolver.py — Citation-Resolver

Extracts and normalizes citations (e.g. "LPI art. 17", "GDPR Art 6(1)(f)")
and links them to source_ids, building a citation graph for EEE audit.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

from agents.base import BaseAgent
from agents.contracts import (
    CanonicalCitation,
    CitationEdge,
    CitationGraph,
    CitationNode,
    CitationResolverInput,
    Jurisdiction,
)

logger = logging.getLogger("lexdomus.agents.citation_resolver")

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "docs_chunks" / "chunks.jsonl"


def _load_known_sources() -> Dict[str, Dict]:
    """Load known sources from chunks.jsonl for linking."""
    sources: Dict[str, Dict] = {}
    if not CHUNKS_PATH.exists():
        return sources
    try:
        with CHUNKS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    meta = rec.get("meta", {})
                    doc_id = rec.get("doc_id", "")
                    if doc_id:
                        sources[doc_id] = meta
                except Exception:
                    continue
    except Exception:
        pass
    return sources


def _match_citation_to_source(
    citation: CanonicalCitation,
    known_sources: Dict[str, Dict],
) -> str:
    """Try to match a canonical citation to a known source_id."""
    # Direct match
    if citation.source_id in known_sources:
        return citation.source_id

    # Fuzzy match by canonical form parts
    parts = citation.canonical.lower().split(":")
    for source_id in known_sources:
        sid_lower = source_id.lower()
        if all(p in sid_lower for p in parts if len(p) > 2):
            return source_id

    return ""


class CitationResolverAgent(BaseAgent[CitationResolverInput, CitationGraph]):
    @property
    def name(self) -> str:
        return "citation-resolver"

    def execute(self, inp: CitationResolverInput) -> CitationGraph:
        known_sources = _load_known_sources()
        existing_ids: Set[str] = set(inp.existing_graph_nodes)

        nodes: List[CitationNode] = []
        edges: List[CitationEdge] = []
        unresolved: List[str] = []
        seen_canonicals: Set[str] = set()

        for citation in inp.canonical_citations:
            if citation.canonical in seen_canonicals:
                continue
            seen_canonicals.add(citation.canonical)

            matched_source = _match_citation_to_source(citation, known_sources)

            if matched_source:
                meta = known_sources.get(matched_source, {})
                nodes.append(
                    CitationNode(
                        canonical=citation.canonical,
                        source_id=matched_source,
                        jurisdiction=citation.jurisdiction,
                        doc_type=meta.get("family", ""),
                        title=meta.get("title", ""),
                    )
                )
                # If citing document is known, create an edge
                if citation.source_id and citation.source_id != matched_source:
                    edges.append(
                        CitationEdge(
                            from_canonical=f"{citation.jurisdiction.value}:{citation.source_id}",
                            to_canonical=citation.canonical,
                            edge_type="cites",
                        )
                    )
            else:
                # Node exists but can't be linked to a local source
                nodes.append(
                    CitationNode(
                        canonical=citation.canonical,
                        source_id=citation.source_id,
                        jurisdiction=citation.jurisdiction,
                    )
                )
                unresolved.append(citation.canonical)

        return CitationGraph(
            nodes=nodes,
            edges=edges,
            unresolved=unresolved,
        )
