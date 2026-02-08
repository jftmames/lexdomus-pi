"""
agents/research/ingest_normalizer.py — Ingest-Normalizer

Parsing PDF/HTML/XML, cleaning, segmenting by legal structure
(artículos, fundamentos, fallo).
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    CanonicalCitation,
    IngestNormalizerInput,
    Jurisdiction,
    NormalizedDoc,
    NormalizedSection,
)

logger = logging.getLogger("lexdomus.agents.ingest_normalizer")

# Patterns for detecting Spanish legal structure
_ART_RE = re.compile(
    r"(?:^|\n)\s*(?:Art[ií]culo|Art\.?)\s+(\d+[\w]*)\b[.\s\-–—]*(.+?)(?=\n\s*(?:Art[ií]culo|Art\.?)\s+\d|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_FUNDAMENTO_RE = re.compile(
    r"(?:FUNDAMENTO|RAZONAMIENTO)\s+(?:DE\s+DERECHO\s+|JURÍDICO\s+)?(\w+)\b[.\s\-–—]*(.+?)(?=\n\s*(?:FUNDAMENTO|RAZONAMIENTO|FALLO)|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_FALLO_RE = re.compile(
    r"(?:^|\n)\s*FALLO\b[.\s\-–—]*(.+)",
    re.IGNORECASE | re.DOTALL,
)

# Citation extraction patterns
_CITE_PATTERNS = [
    # Spanish: LPI art. 17, TRLPI art. 14
    re.compile(r"\b((?:TR)?LPI)\s+art\.?\s*(\d+[\w]*)", re.IGNORECASE),
    # EU: GDPR Art 6(1)(f), Directive 2001/29/CE art. 3
    re.compile(r"\b(GDPR|RGPD)\s+Art\.?\s*(\d+(?:\(\d+\)(?:\([a-z]\))?)?)", re.IGNORECASE),
    re.compile(r"Directiva\s+([\d/]+(?:/CE)?)\s+art\.?\s*(\d+)", re.IGNORECASE),
    # Berne Convention
    re.compile(r"(?:Berna|Berne)\s+art\.?\s*(\d+[\w]*)", re.IGNORECASE),
    # US: 17 USC § 106
    re.compile(r"17\s+U\.?S\.?C\.?\s*§?\s*(\d+)", re.IGNORECASE),
]


def _clean_text(text: str) -> str:
    """Remove excess whitespace, normalize line endings."""
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _segment_by_articles(text: str, source_id: str) -> List[NormalizedSection]:
    """Segment text by article boundaries."""
    sections: List[NormalizedSection] = []
    for m in _ART_RE.finditer(text):
        art_num = m.group(1).strip()
        art_text = m.group(2).strip()
        sections.append(
            NormalizedSection(
                section_id=f"{source_id}#art{art_num}",
                section_type="articulo",
                title=f"Artículo {art_num}",
                text=art_text,
            )
        )
    return sections


def _segment_sentencia(text: str, source_id: str) -> List[NormalizedSection]:
    """Segment a court decision into fundamentos + fallo."""
    sections: List[NormalizedSection] = []
    for m in _FUNDAMENTO_RE.finditer(text):
        num = m.group(1).strip()
        body = m.group(2).strip()
        sections.append(
            NormalizedSection(
                section_id=f"{source_id}#fd{num}",
                section_type="fundamento",
                title=f"Fundamento {num}",
                text=body,
            )
        )
    fallo_m = _FALLO_RE.search(text)
    if fallo_m:
        sections.append(
            NormalizedSection(
                section_id=f"{source_id}#fallo",
                section_type="fallo",
                title="Fallo",
                text=fallo_m.group(1).strip(),
            )
        )
    return sections


def _chunk_by_size(text: str, source_id: str, chunk_size: int = 1000, overlap: int = 100) -> List[NormalizedSection]:
    """Fallback: split into fixed-size chunks with overlap."""
    sections: List[NormalizedSection] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        sections.append(
            NormalizedSection(
                section_id=f"{source_id}#chunk{idx:03d}",
                section_type="chunk",
                title=f"Chunk {idx}",
                text=text[start:end],
            )
        )
        start = end - overlap if end < len(text) else end
        idx += 1
    return sections


def _extract_citations(text: str, source_id: str, jurisdiction: Jurisdiction) -> List[CanonicalCitation]:
    """Extract and normalize legal citations."""
    citations: List[CanonicalCitation] = []
    seen: set = set()

    for pattern in _CITE_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0).strip()
            groups = m.groups()
            # Build canonical form
            if len(groups) >= 2:
                canonical = f"{jurisdiction.value}:{groups[0].upper()}:art{groups[1]}"
            else:
                canonical = f"{jurisdiction.value}:{groups[0]}"

            if canonical not in seen:
                seen.add(canonical)
                citations.append(
                    CanonicalCitation(
                        raw=raw,
                        canonical=canonical,
                        source_id=source_id,
                        jurisdiction=jurisdiction,
                        pinpoint=True,
                    )
                )
    return citations


class IngestNormalizerAgent(BaseAgent[IngestNormalizerInput, NormalizedDoc]):
    @property
    def name(self) -> str:
        return "ingest-normalizer"

    def execute(self, inp: IngestNormalizerInput) -> NormalizedDoc:
        text = _clean_text(inp.raw_content)

        # Try structured segmentation first, fall back to chunks
        sections = _segment_by_articles(text, inp.source_id)
        if not sections:
            sections = _segment_sentencia(text, inp.source_id)
        if not sections:
            sections = _chunk_by_size(text, inp.source_id)

        citations = _extract_citations(text, inp.source_id, inp.jurisdiction)

        return NormalizedDoc(
            source_id=inp.source_id,
            sections=sections,
            canonical_citations=citations,
            metadata={
                "source_origin": inp.source_origin.value,
                "content_type": inp.content_type,
                "jurisdiction": inp.jurisdiction.value,
            },
        )
