"""
orchestration/workflow_engine.py — Workflow engine (coordinator).

Defines the deliberative workflow as a state machine with gates.
Coordinates all agents in the correct order with state persistence
and event emission for traceability.

Workflow steps:
  1. Inquiry Engine -> 4 Issues + risk_flags
  2. Retrieval Planner -> retrieval_plan per issue
  3. Evidence Assembler -> evidence_pack per issue
  4. Contradiction Checker -> conflicts
  5. Drafting Agent -> draft with [SRC:...] citations
  6. EEE Auditor -> score + gaps
  7. [Gate] If score < threshold -> Repair Agent (max 2 iterations)
  8. [Gate] If needs_human -> pause for human input
  9. Finalizer -> PDF + trace + hash
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional

from agents.base import AgentError
from agents.contracts import (
    ContradictionCheckerInput,
    DraftingAgentInput,
    EEEAuditorInput,
    EvidenceAssemblerInput,
    FinalArtifact,
    FinalizerInput,
    GateStatus,
    InquiryEngineInput,
    Jurisdiction,
    RepairAgentInput,
    RetrievalPlannerInput,
    SessionState,
)
from agents.deliberative.inquiry_engine import InquiryEngineAgent
from agents.deliberative.retrieval_planner import RetrievalPlannerAgent
from agents.deliberative.evidence_assembler import EvidenceAssemblerAgent
from agents.deliberative.contradiction_checker import ContradictionCheckerAgent
from agents.deliberative.drafting_agent import DraftingAgent
from agents.deliberative.eee_auditor import EEEAuditorAgent
from agents.deliberative.repair_agent import RepairAgent
from agents.deliberative.finalizer import FinalizerAgent
from orchestration.event_bus import Event, EventBus
from orchestration.state_store import StateStore

logger = logging.getLogger("lexdomus.orchestration.workflow")

MAX_REPAIR_ITERATIONS = 2


class WorkflowStep(str, Enum):
    INQUIRY = "inquiry"
    RETRIEVAL_PLAN = "retrieval_plan"
    EVIDENCE = "evidence"
    CONTRADICTION = "contradiction"
    DRAFT = "draft"
    EEE_AUDIT = "eee_audit"
    REPAIR = "repair"
    HUMAN_GATE = "human_gate"
    FINALIZE = "finalize"
    DONE = "done"


class WorkflowResult:
    """Result of running the full or partial workflow."""

    def __init__(self):
        self.session_state: Optional[SessionState] = None
        self.final_artifact: Optional[FinalArtifact] = None
        self.current_step: WorkflowStep = WorkflowStep.INQUIRY
        self.needs_human_input: bool = False
        self.human_question: str = ""
        self.error: str = ""
        self.latency_ms: float = 0.0


class WorkflowEngine:
    """
    Coordinates the deliberative pipeline end-to-end.

    Instantiate with optional event bus and state store.
    Call run() with a SessionState to execute the full workflow.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        state_store: StateStore | None = None,
    ):
        self.bus = event_bus or EventBus()
        self.store = state_store or StateStore()

        # Instantiate all agents
        self._inquiry = InquiryEngineAgent()
        self._retrieval_planner = RetrievalPlannerAgent()
        self._evidence_assembler = EvidenceAssemblerAgent()
        self._contradiction_checker = ContradictionCheckerAgent()
        self._drafter = DraftingAgent()
        self._eee_auditor = EEEAuditorAgent()
        self._repair = RepairAgent()
        self._finalizer = FinalizerAgent()

    def _emit(self, event_type: str, payload: object, source: str) -> None:
        self.bus.publish(Event(
            event_type=event_type,
            payload=payload,
            source_agent=source,
        ))

    def run(self, state: SessionState) -> WorkflowResult:
        """
        Execute the full deliberative workflow.

        Returns a WorkflowResult with the final artifact or
        a pause point (needs_human_input=True).
        """
        result = WorkflowResult()
        result.session_state = state
        t0 = time.perf_counter()

        try:
            # Step 1: Inquiry Engine
            result.current_step = WorkflowStep.INQUIRY
            inquiry_out = self._inquiry.run(
                InquiryEngineInput(
                    clause=state.clause,
                    jurisdiction=state.jurisdiction,
                    instrument_type=state.instrument_type,
                )
            )
            state.inquiry_output = inquiry_out
            self.store.save(state)
            self._emit("inquiry.done", inquiry_out, "inquiry-engine")

            # Step 2: Retrieval Planner
            result.current_step = WorkflowStep.RETRIEVAL_PLAN
            plans_out = self._retrieval_planner.run(
                RetrievalPlannerInput(
                    issues=inquiry_out.issues,
                    jurisdiction=state.jurisdiction,
                    instrument_type=state.instrument_type,
                )
            )
            state.retrieval_plans = plans_out
            self.store.save(state)
            self._emit("retrieval.planned", plans_out, "retrieval-planner")

            # Step 3: Evidence Assembler
            result.current_step = WorkflowStep.EVIDENCE
            evidence_out = self._evidence_assembler.run(
                EvidenceAssemblerInput(plans=plans_out.plans)
            )
            state.evidence_packs = evidence_out
            self.store.save(state)
            self._emit("evidence.assembled", evidence_out, "evidence-assembler")

            # Step 4: Contradiction Checker
            result.current_step = WorkflowStep.CONTRADICTION
            conflicts_out = self._contradiction_checker.run(
                ContradictionCheckerInput(
                    evidence_packs=evidence_out.evidence_packs,
                    jurisdiction=state.jurisdiction,
                )
            )
            state.conflicts = conflicts_out
            self.store.save(state)
            self._emit("conflicts.checked", conflicts_out, "contradiction-checker")

            # Step 5: Drafting Agent
            result.current_step = WorkflowStep.DRAFT
            draft_out = self._drafter.run(
                DraftingAgentInput(
                    evidence_packs=evidence_out.evidence_packs,
                    conflicts=conflicts_out.conflicts,
                    clause=state.clause,
                    jurisdiction=state.jurisdiction,
                    instrument_type=state.instrument_type,
                )
            )
            state.draft_versions.append(draft_out)
            self.store.save(state)
            self._emit("draft.created", draft_out, "drafting-agent")

            # Step 6: EEE Audit
            result.current_step = WorkflowStep.EEE_AUDIT
            eee_report = self._eee_auditor.run(
                EEEAuditorInput(
                    draft=draft_out,
                    evidence_packs=evidence_out.evidence_packs,
                    conflicts=conflicts_out.conflicts,
                )
            )
            state.eee_reports.append(eee_report)
            self.store.save(state)
            self._emit("eee.audited", eee_report, "eee-auditor")

            # Step 7: Repair loop (max iterations)
            current_draft = draft_out
            current_eee = eee_report

            for repair_iter in range(MAX_REPAIR_ITERATIONS):
                if current_eee.gate_status == GateStatus.OK:
                    break

                result.current_step = WorkflowStep.REPAIR
                repair_out = self._repair.run(
                    RepairAgentInput(
                        draft=current_draft,
                        eee_report=current_eee,
                        evidence_packs=evidence_out.evidence_packs,
                    )
                )
                self._emit("draft.repaired", repair_out, "repair-agent")

                # Check if human input needed
                if repair_out.needs_human_input:
                    result.current_step = WorkflowStep.HUMAN_GATE
                    result.needs_human_input = True
                    result.human_question = repair_out.human_question
                    self.store.save(state)
                    result.latency_ms = (time.perf_counter() - t0) * 1000
                    return result

                # Re-audit the repaired draft
                from agents.contracts import DraftingAgentOutput
                repaired_draft = DraftingAgentOutput(
                    text=repair_out.text,
                    citations=current_draft.citations + repair_out.new_citations,
                    pros=current_draft.pros,
                    cons=current_draft.cons,
                    devils_advocate=current_draft.devils_advocate,
                )
                current_draft = repaired_draft
                state.draft_versions.append(repaired_draft)

                current_eee = self._eee_auditor.run(
                    EEEAuditorInput(
                        draft=repaired_draft,
                        evidence_packs=evidence_out.evidence_packs,
                        conflicts=conflicts_out.conflicts,
                    )
                )
                state.eee_reports.append(current_eee)
                self.store.save(state)

            # Step 8: Finalize
            result.current_step = WorkflowStep.FINALIZE
            final = self._finalizer.run(
                FinalizerInput(
                    text=current_draft.text,
                    citations=current_draft.citations,
                    eee_report=current_eee,
                    session_id=state.session_id,
                )
            )
            state.final_trace = final
            self.store.save(state)
            self._emit("workflow.finalized", final, "finalizer")

            result.final_artifact = final
            result.current_step = WorkflowStep.DONE

        except AgentError as exc:
            result.error = str(exc)
            logger.error("Workflow failed at step %s: %s", result.current_step.value, exc)
        except Exception as exc:
            result.error = f"Unexpected: {exc}"
            logger.error("Workflow unexpected failure: %s", exc, exc_info=True)

        result.latency_ms = (time.perf_counter() - t0) * 1000
        result.session_state = state
        return result
