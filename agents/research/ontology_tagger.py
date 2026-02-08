"""
agents/research/ontology_tagger.py — Ontology-Tagger

Labels each chunk with: jurisdiction, doc type, topic, and
structural signals (definition, exception, deadline, sanction, etc.).
"""
from __future__ import annotations

import logging
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    ChunkMetadata,
    Jurisdiction,
    NormalizedDoc,
    NormalizedSection,
    OntologyTaggerInput,
    OntologyTaggerOutput,
    SignalType,
)

logger = logging.getLogger("lexdomus.agents.ontology_tagger")

# Signal detection patterns
_SIGNAL_PATTERNS = {
    SignalType.DEFINITION: [
        re.compile(r"\bse\s+entender[áa]\s+por\b", re.I),
        re.compile(r"\ba\s+(?:los\s+)?efectos\s+de\b", re.I),
        re.compile(r"\bdefin(?:e|ición|ido)\b", re.I),
        re.compile(r"\bmeans?\b.*\bfor\s+the\s+purposes?\b", re.I),
    ],
    SignalType.EXCEPTION: [
        re.compile(r"\bexcept[oúu]a(?:r|n|ndo|se)?\b", re.I),
        re.compile(r"\bse\s+except[úu]an\b", re.I),
        re.compile(r"\bsin\s+perjuicio\b", re.I),
        re.compile(r"\bsalvo\s+(?:que|lo)\b", re.I),
        re.compile(r"\bnotwithstanding\b", re.I),
        re.compile(r"\bexcept\s+(?:where|when|as)\b", re.I),
        re.compile(r"\bexcepci[oó]n\b", re.I),
    ],
    SignalType.DEADLINE: [
        re.compile(r"\bplazo\s+de\b", re.I),
        re.compile(r"\bdentro\s+de\s+\d+\s+d[ií]as\b", re.I),
        re.compile(r"\bwithin\s+\d+\s+(?:days|months|years)\b", re.I),
        re.compile(r"\bprescri(?:be|pción)\b", re.I),
        re.compile(r"\bcaduc(?:a|idad)\b", re.I),
    ],
    SignalType.SANCTION: [
        re.compile(r"\bsanción\b", re.I),
        re.compile(r"\bmulta\b", re.I),
        re.compile(r"\bindemnizaci[óo]n\b", re.I),
        re.compile(r"\bpenalt(?:y|ies)\b", re.I),
        re.compile(r"\bliabilit(?:y|ies)\b", re.I),
    ],
    SignalType.OBLIGATION: [
        re.compile(r"\bdeber[áa]\b", re.I),
        re.compile(r"\best[áa]\s+obligad[oa]\b", re.I),
        re.compile(r"\bshall\b", re.I),
        re.compile(r"\bmust\b", re.I),
    ],
    SignalType.RIGHT: [
        re.compile(r"\bderecho\s+(?:a|de)\b", re.I),
        re.compile(r"\btendr[áa]\s+derecho\b", re.I),
        re.compile(r"\bfacultad\b", re.I),
        re.compile(r"\bshall\s+(?:be\s+)?entitle[d]?\b", re.I),
    ],
    SignalType.PRESUMPTION: [
        re.compile(r"\bse\s+presume\b", re.I),
        re.compile(r"\bpresunci[óo]n\b", re.I),
        re.compile(r"\bshall\s+be\s+(?:deemed|presumed)\b", re.I),
    ],
}

# Topic detection keywords
_TOPIC_KEYWORDS = {
    "propiedad_intelectual": [
        "propiedad intelectual", "derechos de autor", "copyright",
        "obra", "autor", "cesión", "licencia", "reproducción",
        "distribución", "comunicación pública", "moral",
    ],
    "proteccion_datos": [
        "protección de datos", "datos personales", "RGPD", "GDPR",
        "tratamiento", "consentimiento", "interesado", "responsable",
    ],
    "contratos": [
        "contrato", "cláusula", "obligación", "prestación",
        "resolución", "rescisión", "incumplimiento",
    ],
    "procesal": [
        "demanda", "recurso", "sentencia", "tutela", "jurisdicción",
        "competencia", "medida cautelar", "ejecución",
    ],
}

# Doc-type inference from section_type
_DOCTYPE_MAP = {
    "articulo": "ley",
    "fundamento": "sentencia",
    "fallo": "sentencia",
    "preambulo": "ley",
    "chunk": "otro",
}


def _detect_signals(text: str) -> List[SignalType]:
    found: List[SignalType] = []
    for signal, patterns in _SIGNAL_PATTERNS.items():
        for rx in patterns:
            if rx.search(text):
                found.append(signal)
                break
    return found


def _detect_topic(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for topic, keywords in _TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)


def _infer_doc_type(section: NormalizedSection) -> str:
    return _DOCTYPE_MAP.get(section.section_type, "otro")


class OntologyTaggerAgent(BaseAgent[OntologyTaggerInput, OntologyTaggerOutput]):
    @property
    def name(self) -> str:
        return "ontology-tagger"

    def execute(self, inp: OntologyTaggerInput) -> OntologyTaggerOutput:
        chunks: List[ChunkMetadata] = []
        jurisdiction = Jurisdiction(
            inp.doc.metadata.get("jurisdiction", "ES")
        )

        for section in inp.doc.sections:
            signals = _detect_signals(section.text)
            tema = _detect_topic(section.text)
            doc_type = _infer_doc_type(section)

            chunks.append(
                ChunkMetadata(
                    chunk_id=section.section_id,
                    source_id=inp.doc.source_id,
                    jurisdiction=jurisdiction,
                    doc_type=doc_type,
                    tema=tema,
                    signals=signals,
                )
            )

        return OntologyTaggerOutput(chunks=chunks)
