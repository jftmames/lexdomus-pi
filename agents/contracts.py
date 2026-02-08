"""
agents/contracts.py — Strict JSON contracts (Pydantic v2) for every agent.

Each agent has a typed Input and Output model. All inter-agent communication
goes through these contracts — no loose dicts.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Shared enums & value objects
# ─────────────────────────────────────────────

class Jurisdiction(str, Enum):
    ES = "ES"
    EU = "EU"
    US = "US"
    INT = "INT"


class SourceOrigin(str, Enum):
    BOE = "BOE"
    EUR_LEX = "EUR-Lex"
    WIPO = "WIPO"
    USC = "USC"
    CURIA = "CURIA"
    OTHER = "OTHER"


class ReformType(str, Enum):
    NEW_CONSOLIDATION = "new_consolidation"
    MODIFICATION = "modification"
    DEROGATION = "derogation"
    CORRECTION = "correction"


class SignalType(str, Enum):
    DEFINITION = "definition"
    EXCEPTION = "exception"
    DEADLINE = "deadline"
    SANCTION = "sanction"
    OBLIGATION = "obligation"
    RIGHT = "right"
    PRESUMPTION = "presumption"


class ConflictType(str, Enum):
    JURISDICTION_MIX = "jurisdiction_mix"
    TEMPORAL_CONFLICT = "temporal_conflict"
    HIERARCHY_CONFLICT = "hierarchy_conflict"
    INTERNAL_TENSION = "internal_tension"


class GateStatus(str, Enum):
    OK = "OK"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"
    NEEDS_HUMAN = "NEEDS_HUMAN"


# ─────────────────────────────────────────────
# 2.1 Research Plane contracts
# ─────────────────────────────────────────────

# --- Source-Watcher ---

class ReformEvent(BaseModel):
    """Output of Source-Watcher: a detected legal reform."""
    source_id: str
    source_origin: SourceOrigin
    reform_type: ReformType
    old_version: Optional[str] = None
    new_version: str
    diff_hint: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    jurisdiction: Jurisdiction = Jurisdiction.ES


class SourceWatcherInput(BaseModel):
    """What Source-Watcher needs to run."""
    sources_to_watch: List[SourceOrigin] = Field(
        default=[SourceOrigin.BOE, SourceOrigin.EUR_LEX]
    )
    since: Optional[datetime] = None


class SourceWatcherOutput(BaseModel):
    """What Source-Watcher produces."""
    events: List[ReformEvent] = []
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = []


# --- Ingest-Normalizer ---

class NormalizedSection(BaseModel):
    """A structural section of a legal document."""
    section_id: str
    section_type: str  # e.g. "articulo", "fundamento", "fallo", "preambulo"
    title: str = ""
    text: str
    parent_section_id: Optional[str] = None


class CanonicalCitation(BaseModel):
    """A standardized citation reference."""
    raw: str           # original text, e.g. "LPI art. 17"
    canonical: str     # normalized form, e.g. "ES:LPI:art17"
    source_id: str
    jurisdiction: Jurisdiction
    pinpoint: bool = False


class IngestNormalizerInput(BaseModel):
    """Raw document to normalize."""
    source_id: str
    source_origin: SourceOrigin
    raw_content: str         # PDF/HTML/XML text
    content_type: str = "text"  # "pdf", "html", "xml", "text"
    jurisdiction: Jurisdiction = Jurisdiction.ES


class NormalizedDoc(BaseModel):
    """Output of Ingest-Normalizer."""
    source_id: str
    sections: List[NormalizedSection]
    canonical_citations: List[CanonicalCitation] = []
    metadata: Dict[str, str] = {}


# --- Ontology-Tagger ---

class ChunkMetadata(BaseModel):
    """Output per chunk from Ontology-Tagger."""
    chunk_id: str
    source_id: str
    jurisdiction: Jurisdiction
    doc_type: str          # "ley", "reglamento", "sentencia", "doctrina"
    tema: str              # e.g. "propiedad_intelectual", "proteccion_datos"
    signals: List[SignalType] = []
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OntologyTaggerInput(BaseModel):
    """Sections to tag."""
    doc: NormalizedDoc


class OntologyTaggerOutput(BaseModel):
    """Tagged chunks."""
    chunks: List[ChunkMetadata]


# --- Citation-Resolver ---

class CitationNode(BaseModel):
    """A node in the citation graph."""
    canonical: str
    source_id: str
    jurisdiction: Jurisdiction
    doc_type: str = ""
    title: str = ""


class CitationEdge(BaseModel):
    """A directed edge: from_canonical cites to_canonical."""
    from_canonical: str
    to_canonical: str
    edge_type: str = "cites"  # "cites", "amends", "derogates", "implements"


class CitationResolverInput(BaseModel):
    """Citations to resolve."""
    canonical_citations: List[CanonicalCitation]
    existing_graph_nodes: List[str] = []  # known canonical IDs


class CitationGraph(BaseModel):
    """Output of Citation-Resolver."""
    nodes: List[CitationNode]
    edges: List[CitationEdge]
    unresolved: List[str] = []  # citations that couldn't be linked


# --- Indexer ---

class IndexerInput(BaseModel):
    """Chunks to index."""
    chunks: List[ChunkMetadata]
    texts: Dict[str, str]  # chunk_id -> text
    version_tag: str = "latest"


class IndexerOutput(BaseModel):
    """Confirmation that indices are ready."""
    vector_index_path: str = ""
    lexical_index_path: str = ""
    chunks_indexed: int = 0
    version_tag: str = "latest"
    deprecated_filtered: int = 0


# ─────────────────────────────────────────────
# 2.2 Deliberative Plane contracts
# ─────────────────────────────────────────────

# --- Inquiry Engine ---

class RiskFlag(BaseModel):
    """A detected risk in the input."""
    flag_type: str
    description: str
    severity: str = "medium"  # low, medium, high


class Issue(BaseModel):
    """A strategic question generated by the Inquiry Engine."""
    issue_id: str
    pregunta: str
    encaje_ref: str = ""       # statutory reference
    principio: str = ""        # justification principle
    evidencias_requeridas: List[str] = []
    alternativa: str = ""


class InquiryEngineInput(BaseModel):
    """Input for the Inquiry Engine."""
    clause: str
    jurisdiction: Jurisdiction
    instrument_type: str = "clausula"  # clausula, informe, demanda, dictamen


class InquiryEngineOutput(BaseModel):
    """Exactly 4 Issues + risk flags. NO draft allowed."""
    issues: List[Issue] = Field(..., min_length=1, max_length=4)
    risk_flags: List[RiskFlag] = []
    instrument_type: str = "clausula"


# --- Retrieval Planner ---

class RetrievalQuery(BaseModel):
    """A single retrieval query with filters."""
    query_text: str
    query_type: str = "normativa"  # normativa, jurisprudencia, doctrina
    jurisdiction_filter: Optional[Jurisdiction] = None
    doc_type_filter: Optional[str] = None
    must_have_signals: List[SignalType] = []
    deprecated: bool = False


class RetrievalPlan(BaseModel):
    """Output of Retrieval Planner."""
    context_id: str  # links to the Issue being researched
    queries: List[RetrievalQuery]
    must_have: List[str] = []  # canonical citations that MUST appear


class RetrievalPlannerInput(BaseModel):
    """What Retrieval Planner needs."""
    issues: List[Issue]
    jurisdiction: Jurisdiction
    instrument_type: str = "clausula"


class RetrievalPlannerOutput(BaseModel):
    """Plans for all issues."""
    plans: List[RetrievalPlan]


# --- Evidence Assembler ---

class SupportingSource(BaseModel):
    """A source that supports or counters a claim."""
    chunk_id: str
    source_id: str
    canonical_citation: str
    text_excerpt: str
    jurisdiction: Jurisdiction
    doc_type: str = ""
    pinpoint: bool = False
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class Claim(BaseModel):
    """A micro-assertion backed by evidence, not yet drafted as clause text."""
    claim_id: str
    statement: str
    supporting_sources: List[SupportingSource] = []
    counter_sources: List[SupportingSource] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidencePack(BaseModel):
    """Output of Evidence Assembler."""
    context_id: str
    claims: List[Claim]
    supporting_sources: List[SupportingSource] = []
    counter_sources: List[SupportingSource] = []
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidenceAssemblerInput(BaseModel):
    """Retrieval plans to execute."""
    plans: List[RetrievalPlan]


class EvidenceAssemblerOutput(BaseModel):
    """Evidence packs for all issues."""
    evidence_packs: List[EvidencePack]


# --- Contradiction / Jurisdiction Checker ---

class Conflict(BaseModel):
    """A detected conflict or tension."""
    conflict_type: ConflictType
    description: str
    involved_sources: List[str] = []  # canonical citations
    required_resolution: str = ""


class ContradictionCheckerInput(BaseModel):
    """Evidence to check for contradictions."""
    evidence_packs: List[EvidencePack]
    jurisdiction: Jurisdiction


class ContradictionCheckerOutput(BaseModel):
    """Detected conflicts."""
    conflicts: List[Conflict]
    jurisdiction_clean: bool = True  # no mix without bridge


# --- Drafting Agent ---

class DraftCitation(BaseModel):
    """An anchored citation in the draft text."""
    marker: str        # e.g. "[SRC:chunk_042]"
    chunk_id: str
    canonical: str
    text_excerpt: str = ""


class DraftingAgentInput(BaseModel):
    """Evidence pack + context to draft from."""
    evidence_packs: List[EvidencePack]
    conflicts: List[Conflict] = []
    clause: str
    jurisdiction: Jurisdiction
    instrument_type: str = "clausula"


class DraftingAgentOutput(BaseModel):
    """Draft with anchored citations."""
    text: str
    citations: List[DraftCitation]
    pros: List[str] = []
    cons: List[str] = []
    devils_advocate: Dict[str, str] = {}


# --- EEE Auditor ---

class EEEGap(BaseModel):
    """A specific gap identified by the auditor."""
    gap_type: str       # "missing_article", "weak_citation", "jurisdiction_conflict"
    description: str
    affected_section: str = ""
    severity: str = "medium"


class EEEAuditorInput(BaseModel):
    """Draft to audit."""
    draft: DraftingAgentOutput
    evidence_packs: List[EvidencePack]
    conflicts: List[Conflict] = []


class EEEReport(BaseModel):
    """Output of EEE Auditor: score 0-100 + gap list."""
    score_T: float = Field(default=0.0, ge=0.0, le=100.0)  # Traceability
    score_J: float = Field(default=0.0, ge=0.0, le=100.0)  # Justification
    score_P: float = Field(default=0.0, ge=0.0, le=100.0)  # Plurality
    score_total: float = Field(default=0.0, ge=0.0, le=100.0)
    missing_gaps: List[EEEGap] = []
    gate_status: GateStatus = GateStatus.NO_CONCLUYENTE


# --- Repair Agent ---

class DraftChange(BaseModel):
    """A specific change made during repair."""
    change_type: str  # "insert_citation", "rewrite_section", "add_bridge"
    description: str
    old_text: str = ""
    new_text: str = ""


class RepairAgentInput(BaseModel):
    """Draft + EEE report to repair."""
    draft: DraftingAgentOutput
    eee_report: EEEReport
    evidence_packs: List[EvidencePack]


class RepairAgentOutput(BaseModel):
    """Repaired draft or request for more info."""
    text: str
    changes: List[DraftChange] = []
    new_citations: List[DraftCitation] = []
    needs_human_input: bool = False
    human_question: str = ""  # if gap is epistemic, not documental


# --- Finalizer ---

class FinalizerInput(BaseModel):
    """Final draft to package."""
    text: str
    citations: List[DraftCitation]
    eee_report: EEEReport
    session_id: str


class FinalArtifact(BaseModel):
    """Output of Finalizer: packaged deliverable."""
    pdf_path: str = ""
    pdf_hash: str = ""
    signature: str = ""
    trace: Dict[str, object] = {}  # full reasoning trace
    eee_summary: Dict[str, float] = {}


# ─────────────────────────────────────────────
# 3.2 Session state
# ─────────────────────────────────────────────

class SessionState(BaseModel):
    """Minimal state tracked per deliberation session."""
    session_id: str
    context_id: str = ""                    # chosen issue
    jurisdiction: Jurisdiction = Jurisdiction.ES
    clause: str = ""
    instrument_type: str = "clausula"
    inquiry_output: Optional[InquiryEngineOutput] = None
    retrieval_plans: Optional[RetrievalPlannerOutput] = None
    evidence_packs: Optional[EvidenceAssemblerOutput] = None
    conflicts: Optional[ContradictionCheckerOutput] = None
    draft_versions: List[DraftingAgentOutput] = []
    eee_reports: List[EEEReport] = []
    final_trace: Optional[FinalArtifact] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
