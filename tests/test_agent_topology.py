"""
tests/test_agent_topology.py — Tests for the full agent topology.

Tests contracts, individual agents, orchestration, and guardrails.
Run with: python -m pytest tests/test_agent_topology.py -v
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from agents.contracts import (
    CanonicalCitation,
    ChunkMetadata,
    CitationResolverInput,
    Claim,
    Conflict,
    ConflictType,
    ContradictionCheckerInput,
    ContradictionCheckerOutput,
    DraftCitation,
    DraftingAgentInput,
    DraftingAgentOutput,
    EEEAuditorInput,
    EEEReport,
    EvidenceAssemblerInput,
    EvidenceAssemblerOutput,
    EvidencePack,
    FinalArtifact,
    FinalizerInput,
    GateStatus,
    IndexerInput,
    IngestNormalizerInput,
    InquiryEngineInput,
    InquiryEngineOutput,
    Issue,
    Jurisdiction,
    NormalizedDoc,
    NormalizedSection,
    OntologyTaggerInput,
    ReformEvent,
    ReformType,
    RepairAgentInput,
    RepairAgentOutput,
    RetrievalPlan,
    RetrievalPlannerInput,
    RetrievalQuery,
    RiskFlag,
    SessionState,
    SignalType,
    SourceOrigin,
    SourceWatcherInput,
    SupportingSource,
)


# ──────────────────────────────────────────
# Contract tests — verify Pydantic models
# ──────────────────────────────────────────

class TestContracts:
    def test_reform_event(self):
        e = ReformEvent(
            source_id="es_lpi",
            source_origin=SourceOrigin.BOE,
            reform_type=ReformType.MODIFICATION,
            new_version="abc123",
        )
        assert e.source_id == "es_lpi"
        data = e.model_dump()
        assert "source_origin" in data

    def test_inquiry_engine_output_max_4_issues(self):
        issues = [
            Issue(issue_id=f"ISS-{i}", pregunta=f"Q{i}")
            for i in range(4)
        ]
        out = InquiryEngineOutput(issues=issues, risk_flags=[])
        assert len(out.issues) == 4

    def test_inquiry_engine_output_rejects_5_issues(self):
        issues = [
            Issue(issue_id=f"ISS-{i}", pregunta=f"Q{i}")
            for i in range(5)
        ]
        with pytest.raises(Exception):
            InquiryEngineOutput(issues=issues, risk_flags=[])

    def test_inquiry_engine_output_rejects_0_issues(self):
        with pytest.raises(Exception):
            InquiryEngineOutput(issues=[], risk_flags=[])

    def test_session_state_roundtrip(self):
        state = SessionState(session_id="test_001", clause="test", jurisdiction=Jurisdiction.ES)
        data = state.model_dump_json()
        restored = SessionState.model_validate_json(data)
        assert restored.session_id == "test_001"

    def test_eee_report_score_bounds(self):
        r = EEEReport(score_T=100.0, score_J=0.0, score_P=50.0, score_total=50.0)
        assert r.score_T == 100.0
        assert r.score_J == 0.0

    def test_evidence_pack(self):
        src = SupportingSource(
            chunk_id="es_lpi#art17",
            source_id="es_lpi",
            canonical_citation="ES:LPI:art17",
            text_excerpt="Texto...",
            jurisdiction=Jurisdiction.ES,
            pinpoint=True,
            relevance_score=0.8,
        )
        claim = Claim(
            claim_id="CLM-001",
            statement="El art. 17 establece...",
            supporting_sources=[src],
            confidence=0.8,
        )
        pack = EvidencePack(
            context_id="ISS-001",
            claims=[claim],
            supporting_sources=[src],
            coverage_ratio=1.0,
        )
        assert pack.claims[0].supporting_sources[0].pinpoint is True


# ──────────────────────────────────────────
# Research Plane agent tests
# ──────────────────────────────────────────

class TestResearchPlane:
    def test_source_watcher(self):
        from agents.research.source_watcher import SourceWatcherAgent
        agent = SourceWatcherAgent()
        result = agent.run(SourceWatcherInput(sources_to_watch=[SourceOrigin.BOE]))
        assert hasattr(result, "events")
        assert hasattr(result, "checked_at")

    def test_ingest_normalizer_articles(self):
        from agents.research.ingest_normalizer import IngestNormalizerAgent
        agent = IngestNormalizerAgent()
        text = """
        Artículo 17. Derechos de explotación
        Corresponde al autor el ejercicio exclusivo de los derechos de explotación.

        Artículo 18. Reproducción
        Se entiende por reproducción la fijación directa o indirecta.
        """
        result = agent.run(IngestNormalizerInput(
            source_id="es_lpi",
            source_origin=SourceOrigin.BOE,
            raw_content=text,
            jurisdiction=Jurisdiction.ES,
        ))
        assert len(result.sections) >= 2
        assert result.sections[0].section_type == "articulo"

    def test_ingest_normalizer_citations(self):
        from agents.research.ingest_normalizer import IngestNormalizerAgent
        agent = IngestNormalizerAgent()
        text = "Según LPI art. 14 y Berna art. 6bis, los derechos morales son irrenunciables."
        result = agent.run(IngestNormalizerInput(
            source_id="test_doc",
            source_origin=SourceOrigin.BOE,
            raw_content=text,
            jurisdiction=Jurisdiction.ES,
        ))
        assert len(result.canonical_citations) >= 1

    def test_ontology_tagger(self):
        from agents.research.ontology_tagger import OntologyTaggerAgent
        agent = OntologyTaggerAgent()
        doc = NormalizedDoc(
            source_id="es_lpi",
            sections=[
                NormalizedSection(
                    section_id="es_lpi#art14",
                    section_type="articulo",
                    title="Artículo 14",
                    text="Se entiende por reproducción la fijación de la obra en un medio que permita su distribución.",
                ),
            ],
            metadata={"jurisdiction": "ES"},
        )
        result = agent.run(OntologyTaggerInput(doc=doc))
        assert len(result.chunks) == 1
        assert result.chunks[0].jurisdiction == Jurisdiction.ES

    def test_ontology_tagger_signals(self):
        from agents.research.ontology_tagger import OntologyTaggerAgent
        agent = OntologyTaggerAgent()
        doc = NormalizedDoc(
            source_id="test",
            sections=[
                NormalizedSection(
                    section_id="test#s1",
                    section_type="articulo",
                    text="El plazo de prescripción será de 5 años. Se exceptúan los casos previstos en el artículo siguiente.",
                ),
            ],
            metadata={"jurisdiction": "ES"},
        )
        result = agent.run(OntologyTaggerInput(doc=doc))
        signals = result.chunks[0].signals
        assert SignalType.DEADLINE in signals
        assert SignalType.EXCEPTION in signals

    def test_citation_resolver(self):
        from agents.research.citation_resolver import CitationResolverAgent
        agent = CitationResolverAgent()
        result = agent.run(CitationResolverInput(
            canonical_citations=[
                CanonicalCitation(
                    raw="LPI art. 17",
                    canonical="ES:LPI:art17",
                    source_id="test_doc",
                    jurisdiction=Jurisdiction.ES,
                    pinpoint=True,
                ),
            ],
        ))
        assert hasattr(result, "nodes")
        assert hasattr(result, "edges")


# ──────────────────────────────────────────
# Deliberative Plane agent tests
# ──────────────────────────────────────────

class TestDeliberativePlane:
    SAMPLE_CLAUSE = (
        "El Autor cede al Editor, con carácter exclusivo y para todo el mundo, "
        "todos los derechos de explotación sobre la Obra, incluyendo reproducción, "
        "distribución y comunicación pública, por la duración máxima permitida por la ley. "
        "El Autor renuncia a todos sus derechos morales."
    )

    def test_inquiry_engine_produces_max_4_issues(self):
        from agents.deliberative.inquiry_engine import InquiryEngineAgent
        agent = InquiryEngineAgent()
        result = agent.run(InquiryEngineInput(
            clause=self.SAMPLE_CLAUSE,
            jurisdiction=Jurisdiction.ES,
        ))
        assert 1 <= len(result.issues) <= 4
        assert isinstance(result.risk_flags, list)

    def test_inquiry_engine_detects_moral_waiver_risk(self):
        from agents.deliberative.inquiry_engine import InquiryEngineAgent
        agent = InquiryEngineAgent()
        result = agent.run(InquiryEngineInput(
            clause=self.SAMPLE_CLAUSE,
            jurisdiction=Jurisdiction.ES,
        ))
        risk_types = {rf.flag_type for rf in result.risk_flags}
        assert "renuncia_moral_general" in risk_types

    def test_retrieval_planner(self):
        from agents.deliberative.retrieval_planner import RetrievalPlannerAgent
        agent = RetrievalPlannerAgent()
        issues = [
            Issue(
                issue_id="ISS-001",
                pregunta="¿Qué derechos se transfieren?",
                encaje_ref="LPI art. 17-23",
            ),
        ]
        result = agent.run(RetrievalPlannerInput(
            issues=issues,
            jurisdiction=Jurisdiction.ES,
        ))
        assert len(result.plans) == 1
        assert len(result.plans[0].queries) >= 1

    def test_evidence_assembler(self):
        from agents.deliberative.evidence_assembler import EvidenceAssemblerAgent
        agent = EvidenceAssemblerAgent()
        plans = [
            RetrievalPlan(
                context_id="ISS-001",
                queries=[
                    RetrievalQuery(
                        query_text="derechos explotación LPI",
                        query_type="normativa",
                        jurisdiction_filter=Jurisdiction.ES,
                    ),
                ],
            ),
        ]
        result = agent.run(EvidenceAssemblerInput(plans=plans))
        assert len(result.evidence_packs) == 1

    def test_contradiction_checker_detects_jurisdiction_mix(self):
        from agents.deliberative.contradiction_checker import ContradictionCheckerAgent
        agent = ContradictionCheckerAgent()
        packs = [
            EvidencePack(
                context_id="ISS-001",
                claims=[],
                supporting_sources=[
                    SupportingSource(
                        chunk_id="es_lpi#art17",
                        source_id="es_lpi",
                        canonical_citation="LPI art. 17",
                        text_excerpt="...",
                        jurisdiction=Jurisdiction.ES,
                    ),
                    SupportingSource(
                        chunk_id="us_usc#s106",
                        source_id="us_usc",
                        canonical_citation="17 USC § 106",
                        text_excerpt="...",
                        jurisdiction=Jurisdiction.US,
                    ),
                ],
            ),
        ]
        result = agent.run(ContradictionCheckerInput(
            evidence_packs=packs,
            jurisdiction=Jurisdiction.ES,
        ))
        assert not result.jurisdiction_clean
        assert any(c.conflict_type == ConflictType.JURISDICTION_MIX for c in result.conflicts)

    def test_drafting_agent(self):
        from agents.deliberative.drafting_agent import DraftingAgent
        agent = DraftingAgent()
        packs = [
            EvidencePack(
                context_id="ISS-001",
                claims=[
                    Claim(
                        claim_id="CLM-001",
                        statement="El art. 17 establece derechos exclusivos",
                        supporting_sources=[
                            SupportingSource(
                                chunk_id="es_lpi#art17",
                                source_id="es_lpi",
                                canonical_citation="LPI art. 17",
                                text_excerpt="Derechos de explotación...",
                                jurisdiction=Jurisdiction.ES,
                                pinpoint=True,
                                relevance_score=0.9,
                            ),
                        ],
                        confidence=0.9,
                    ),
                ],
                supporting_sources=[
                    SupportingSource(
                        chunk_id="es_lpi#art17",
                        source_id="es_lpi",
                        canonical_citation="LPI art. 17",
                        text_excerpt="Derechos de explotación...",
                        jurisdiction=Jurisdiction.ES,
                        pinpoint=True,
                        relevance_score=0.9,
                    ),
                ],
                coverage_ratio=1.0,
            ),
        ]
        result = agent.run(DraftingAgentInput(
            evidence_packs=packs,
            clause="Test clause",
            jurisdiction=Jurisdiction.ES,
        ))
        assert "[SRC:" in result.text
        assert len(result.citations) >= 1

    def test_eee_auditor(self):
        from agents.deliberative.eee_auditor import EEEAuditorAgent
        agent = EEEAuditorAgent()
        draft = DraftingAgentOutput(
            text="- Afirmación con cita [SRC:es_lpi#art17]\n- Sin cita aquí",
            citations=[
                DraftCitation(marker="[SRC:es_lpi#art17]", chunk_id="es_lpi#art17", canonical="LPI art. 17"),
            ],
            pros=["Pro 1"],
            cons=["Con 1"],
            devils_advocate={"hipotesis": "Alt", "lectura": "Lectura", "cuando_mejor": "Cuando"},
        )
        packs = [EvidencePack(context_id="ISS-001", claims=[], coverage_ratio=0.5)]
        result = agent.run(EEEAuditorInput(draft=draft, evidence_packs=packs))
        assert 0 <= result.score_T <= 100
        assert 0 <= result.score_J <= 100
        assert 0 <= result.score_P <= 100

    def test_repair_agent(self):
        from agents.deliberative.repair_agent import RepairAgent
        agent = RepairAgent()
        draft = DraftingAgentOutput(
            text="- Afirmación sin cita\n- Otra afirmación",
            citations=[],
            pros=["Pro"],
            cons=["Con"],
        )
        eee = EEEReport(
            score_T=30.0, score_J=50.0, score_P=50.0, score_total=43.3,
            missing_gaps=[],
            gate_status=GateStatus.NO_CONCLUYENTE,
        )
        result = agent.run(RepairAgentInput(
            draft=draft,
            eee_report=eee,
            evidence_packs=[],
        ))
        assert isinstance(result.text, str)

    def test_finalizer(self):
        from agents.deliberative.finalizer import FinalizerAgent
        agent = FinalizerAgent()
        eee = EEEReport(
            score_T=80.0, score_J=70.0, score_P=60.0, score_total=70.0,
            gate_status=GateStatus.OK,
        )
        result = agent.run(FinalizerInput(
            text="Final text",
            citations=[],
            eee_report=eee,
            session_id="test_session_001",
        ))
        assert result.pdf_hash
        assert result.signature
        assert result.trace["session_id"] == "test_session_001"


# ──────────────────────────────────────────
# Orchestration tests
# ──────────────────────────────────────────

class TestOrchestration:
    def test_event_bus(self):
        from orchestration.event_bus import Event, EventBus
        bus = EventBus()
        received = []
        bus.subscribe("test.event", lambda e: received.append(e))
        bus.publish(Event(event_type="test.event", payload={"key": "value"}, source_agent="test"))
        assert len(received) == 1
        assert received[0].payload["key"] == "value"

    def test_state_store(self, tmp_path):
        from orchestration.state_store import StateStore
        store = StateStore(base_dir=tmp_path)
        state = SessionState(session_id="test_ss", clause="test", jurisdiction=Jurisdiction.ES)
        store.save(state)
        loaded = store.get("test_ss")
        assert loaded is not None
        assert loaded.clause == "test"

    def test_session_manager(self, tmp_path):
        from orchestration.state_store import StateStore
        from orchestration.session import SessionManager
        store = StateStore(base_dir=tmp_path)
        mgr = SessionManager(store=store)
        state = mgr.create(clause="test clause", jurisdiction=Jurisdiction.ES)
        assert state.session_id.startswith("ses_")
        assert mgr.get(state.session_id) is not None

    def test_full_workflow(self, tmp_path):
        """Integration test: run the full deliberative workflow."""
        from orchestration.event_bus import EventBus
        from orchestration.state_store import StateStore
        from orchestration.workflow_engine import WorkflowEngine

        bus = EventBus()
        store = StateStore(base_dir=tmp_path)
        engine = WorkflowEngine(event_bus=bus, state_store=store)

        state = SessionState(
            session_id="integration_test",
            clause=(
                "El Autor cede al Editor todos los derechos de explotación "
                "sobre la Obra, por la duración máxima permitida."
            ),
            jurisdiction=Jurisdiction.ES,
            instrument_type="clausula",
        )

        result = engine.run(state)

        # Should complete (possibly with NO_CONCLUYENTE but no error)
        assert result.error == "", f"Workflow failed: {result.error}"
        assert result.session_state is not None
        assert result.session_state.inquiry_output is not None
        assert len(result.session_state.inquiry_output.issues) >= 1
        assert result.session_state.draft_versions  # at least one draft
        assert result.session_state.eee_reports  # at least one audit

        # Check events were emitted
        assert len(bus.history()) >= 5  # inquiry + plan + evidence + conflicts + draft + eee


# ──────────────────────────────────────────
# Guardrails tests
# ──────────────────────────────────────────

class TestGuardrails:
    def test_inquiry_max_4_rule(self):
        from guardrails.rules import GuardrailsEngine
        engine = GuardrailsEngine()

        # Valid: 4 issues
        valid = InquiryEngineOutput(
            issues=[Issue(issue_id=f"ISS-{i}", pregunta=f"Q{i}") for i in range(4)],
            risk_flags=[],
        )
        violations = engine.validate_inquiry(valid)
        assert len(violations) == 0

    def test_draft_citation_rule(self):
        from guardrails.rules import GuardrailsEngine
        engine = GuardrailsEngine()

        draft = DraftingAgentOutput(
            text="- Afirmación con cita [SRC:x]\n- Afirmación sin cita\n- Otra sin cita",
            citations=[],
        )
        violations = engine.validate_draft_citations(draft)
        assert len(violations) == 1
        assert violations[0].rule == "MANDATORY_CITATION"

    def test_jurisdiction_separation_rule(self):
        from guardrails.rules import GuardrailsEngine
        engine = GuardrailsEngine()

        # Conflict without resolution
        conflicts = ContradictionCheckerOutput(
            conflicts=[
                Conflict(
                    conflict_type=ConflictType.JURISDICTION_MIX,
                    description="Mix ES/US",
                    required_resolution="",
                ),
            ],
            jurisdiction_clean=False,
        )
        violations = engine.validate_jurisdiction_separation(conflicts)
        assert len(violations) == 1
        assert violations[0].rule == "JURISDICTION_SEPARATION"

    def test_human_gate_review(self):
        from guardrails.gates import HumanGate
        gate = HumanGate()

        draft = DraftingAgentOutput(
            text="Draft text [SRC:x]",
            citations=[DraftCitation(marker="[SRC:x]", chunk_id="x", canonical="LPI art. 17")],
            pros=["Pro"],
            cons=["Con"],
        )
        eee = EEEReport(
            score_T=50.0, score_J=50.0, score_P=50.0, score_total=50.0,
            gate_status=GateStatus.NEEDS_HUMAN,
        )
        packs = [EvidencePack(
            context_id="ISS-001",
            claims=[],
            supporting_sources=[
                SupportingSource(
                    chunk_id="x", source_id="s", canonical_citation="LPI art. 17",
                    text_excerpt="...", jurisdiction=Jurisdiction.ES,
                ),
            ],
        )]

        review = gate.build_review(draft, eee, packs)
        assert review.gate_status == "NEEDS_HUMAN"
        assert len(review.evidence_summary) == 1
        assert review.eee_scores["T"] == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
