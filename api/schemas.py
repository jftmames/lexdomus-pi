"""Versioned request/response boundary for the technical ES pilot."""
from typing import Annotated, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from lex_domus.contracts import citation_from_record

CONTRACT_VERSION = "0.2"
MAX_CLAUSE_CHARACTERS = 5000
NonEmpty = Annotated[str, Field(min_length=1)]


class ContractModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class AnalyzeIn(ContractModel):
    clause: Annotated[str, Field(min_length=1, max_length=MAX_CLAUSE_CHARACTERS)]
    jurisdiction: Literal["ES"]

    @field_validator("clause")
    @classmethod
    def meaningful_unicode(cls, value: str) -> str:
        # Same blank predicate as JS /^[\s\u001c-\u001f\u0085]*$/u.
        if all(char.isspace() or char == "\ufeff" for char in value):
            raise ValueError("Blank clause")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Unpaired Unicode surrogate")
        return value  # preserve spaces, line breaks and wording exactly


class CitationMeta(ContractModel):
    doc_id: NonEmpty
    source: NonEmpty
    jurisdiction: NonEmpty
    ref_url: NonEmpty
    title: str = ""
    family: str = ""
    ref_label: str = ""
    pinpoint: bool = False
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class Citation(ContractModel):
    text: NonEmpty
    meta: CitationMeta

    @model_validator(mode="before")
    @classmethod
    def valid_provenance(cls, value):
        normalized = citation_from_record(value)
        if normalized is None:
            raise ValueError("Invalid citation provenance")
        return normalized


class InquiryNode(ContractModel):
    pregunta: NonEmpty
    encaje_ref: str = ""
    principio: str = ""
    evidencias_requeridas: List[str] = Field(default_factory=list)
    alternativa: str = ""


class Retrieval(ContractModel):
    status: Literal["OK", "NO_EVIDENCE"]
    citations: List[Citation]

    @model_validator(mode="after")
    def consistent_status(self):
        if (self.status == "OK") != bool(self.citations):
            raise ValueError("Retrieval status and evidence disagree")
        return self


class NodeResult(ContractModel):
    node: InquiryNode
    retrieval: Retrieval
    used_query: NonEmpty


class Gate(ContractModel):
    status: Literal["OK", "NO_EVIDENCE"]


class DevilsAdvocate(ContractModel):
    hipotesis: str = ""
    lectura: str = ""
    cuando_mejor: str = ""


class Opinion(ContractModel):
    analysis_md: NonEmpty
    pros: List[str]
    cons: List[str]
    devils_advocate: DevilsAdvocate

    @field_validator("analysis_md")
    @classmethod
    def nonblank_analysis(cls, value: str) -> str:
        if all(char.isspace() or char == "\ufeff" for char in value):
            raise ValueError("Blank opinion")
        return value


class EeeMetrics(ContractModel):
    T: float
    J: float
    P: float


class AnalyzeResponse(ContractModel):
    contract_version: Literal["0.2"] = CONTRACT_VERSION
    request_id: UUID
    status: Literal["DRAFT_REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"]
    message: str
    review_required: Literal[True] = True
    engine: Literal["LLM", "MOCK", "NOT_RUN"]
    per_node: Annotated[List[NodeResult], Field(min_length=1)]
    flags: List[str] = Field(default_factory=list)
    gate: Gate
    opinion: Optional[Opinion] = None
    alternative_clause: Optional[str] = None
    EEE: Optional[EeeMetrics] = None
    latency_ms: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def consistent_result(self):
        has_evidence = any(node.retrieval.citations for node in self.per_node)
        draft = self.status == "DRAFT_REVIEW_REQUIRED"
        if has_evidence != (self.gate.status == "OK") or draft != has_evidence:
            raise ValueError("Result status and evidence disagree")
        if draft and (self.engine == "NOT_RUN" or self.opinion is None):
            raise ValueError("Draft requires a generated opinion")
        if not draft and (self.engine != "NOT_RUN" or self.opinion is not None
                          or self.alternative_clause is not None or self.EEE is not None):
            raise ValueError("Insufficient evidence must not contain generated advice")
        return self


class InputIssue(ContractModel):
    field: Literal["body", "clause", "jurisdiction"]
    code: str


class ErrorResponse(ContractModel):
    contract_version: Literal["0.2"] = CONTRACT_VERSION
    request_id: UUID
    status: Literal["INVALID_INPUT", "OUT_OF_SCOPE", "TECHNICAL_ERROR"]
    message: str
    errors: List[InputIssue] = Field(default_factory=list)
