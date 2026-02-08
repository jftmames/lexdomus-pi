"""
agents/deliberative/inquiry_engine.py — Inquiry Engine (Paso 3→4)

Detects ambiguity, risks, jurisdiction, instrument type.
Produces EXACTLY ≤4 Issues (strategic questions) + risk_flags.

HARD RULE: this agent MUST NOT produce any draft or final answer.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    InquiryEngineInput,
    InquiryEngineOutput,
    Issue,
    Jurisdiction,
    RiskFlag,
)

logger = logging.getLogger("lexdomus.agents.inquiry_engine")

# Reuse existing decomposition if available
try:
    from verdiktia.inquiry_engine import decompose_clause as _legacy_decompose
except ImportError:
    _legacy_decompose = None

# Risk detection patterns (extends flagger.py)
_RISK_PATTERNS = {
    "renuncia_moral_general": {
        "patterns": [
            re.compile(r"renunci[ae]\s+a\s+todos?\s+sus\s+derechos\s+morales", re.I),
            re.compile(r"waiv(?:e|er).{0,20}moral\s+rights", re.I),
        ],
        "severity": "high",
        "description": "Pretende renuncia general a derechos morales (irrenunciables en ES/EU).",
    },
    "territorialidad_ambigua": {
        "patterns": [
            re.compile(r"\bworldwide\b", re.I),
            re.compile(r"en\s+cualquier\s+pa[ií]s", re.I),
        ],
        "severity": "medium",
        "description": "Alcance territorial ambiguo sin puente jurisdiccional explícito.",
    },
    "modalidades_genericas": {
        "patterns": [
            re.compile(r"cualquier\s+soporte\s+conocido\s+o\s+por\s+conocerse", re.I),
            re.compile(r"any\s+media\s+now\s+known\s+or\s+hereafter\s+devised", re.I),
        ],
        "severity": "medium",
        "description": "Modalidades de explotación genéricas sin limitación.",
    },
    "cesion_futura_generica": {
        "patterns": [
            re.compile(r"obras?\s+futuras?\s+del\s+autor", re.I),
            re.compile(r"future\s+works", re.I),
        ],
        "severity": "high",
        "description": "Cesión sobre obras futuras (nula en muchas jurisdicciones).",
    },
    "ausencia_plazo": {
        "patterns": [
            re.compile(r"\ba\s+perpetuidad\b", re.I),
            re.compile(r"\bin\s+perpetuity\b", re.I),
            re.compile(r"\birrevocable\b", re.I),
        ],
        "severity": "medium",
        "description": "Plazo indefinido o irrevocabilidad sin matices.",
    },
}


def _detect_risks(clause: str) -> List[RiskFlag]:
    flags: List[RiskFlag] = []
    for flag_type, config in _RISK_PATTERNS.items():
        for rx in config["patterns"]:
            if rx.search(clause):
                flags.append(
                    RiskFlag(
                        flag_type=flag_type,
                        description=config["description"],
                        severity=config["severity"],
                    )
                )
                break
    return flags


def _build_issues_heuristic(
    clause: str,
    jurisdiction: Jurisdiction,
    instrument_type: str,
    risks: List[RiskFlag],
) -> List[Issue]:
    """
    Deterministic issue generation. Produces up to 4 strategic questions
    based on the clause structure and detected risks.
    """
    issues: List[Issue] = []

    # Issue 1: always — scope of rights transferred/licensed
    issues.append(
        Issue(
            issue_id="ISS-001",
            pregunta="¿Qué derechos patrimoniales se transfieren o licencian, y con qué alcance?",
            encaje_ref="LPI art. 17-23; Berna art. 6bis" if jurisdiction in (Jurisdiction.ES, Jurisdiction.EU) else "17 USC § 106",
            principio="seguridad jurídica / tipicidad de las modalidades",
            evidencias_requeridas=["Texto de la cláusula", "Artículos aplicables por modalidad"],
            alternativa="Licencia no exclusiva limitada a soportes expresamente listados",
        )
    )

    # Issue 2: moral rights (especially if risk detected)
    moral_risk = any(r.flag_type == "renuncia_moral_general" for r in risks)
    if moral_risk or jurisdiction in (Jurisdiction.ES, Jurisdiction.EU, Jurisdiction.INT):
        issues.append(
            Issue(
                issue_id="ISS-002",
                pregunta="¿Se respetan los derechos morales del autor y qué tratamiento reciben?",
                encaje_ref="LPI art. 14; Berna art. 6bis",
                principio="favor auctoris / irrenunciabilidad",
                evidencias_requeridas=["Referencia a paternidad e integridad", "Previsión de modificaciones"],
                alternativa="Prever autorización previa para modificaciones sustanciales, preservando paternidad",
            )
        )

    # Issue 3: territorial/temporal scope
    territory_risk = any(r.flag_type in ("territorialidad_ambigua", "ausencia_plazo") for r in risks)
    if territory_risk or True:  # always relevant
        issues.append(
            Issue(
                issue_id="ISS-003",
                pregunta="¿Son adecuados el alcance territorial y temporal de la cesión/licencia?",
                encaje_ref="LPI art. 43; Directiva 2001/29/CE" if jurisdiction != Jurisdiction.US else "17 USC § 201-205",
                principio="proporcionalidad / limitación temporal",
                evidencias_requeridas=["Territorio explícito", "Plazo determinado o determinable"],
                alternativa="Limitar a territorio y plazo concretos; incluir cláusula de revisión",
            )
        )

    # Issue 4: jurisdiction-specific compliance
    if len(issues) < 4:
        if jurisdiction == Jurisdiction.ES:
            issues.append(
                Issue(
                    issue_id="ISS-004",
                    pregunta="¿Cumple la cláusula con los requisitos formales del TRLPI y normativa aplicable?",
                    encaje_ref="TRLPI art. 43-50",
                    principio="legalidad / forma ad solemnitatem",
                    evidencias_requeridas=["Forma escrita", "Identificación precisa de la obra"],
                    alternativa="Incorporar identificación precisa de la obra y firma de ambas partes",
                )
            )
        elif jurisdiction == Jurisdiction.EU:
            issues.append(
                Issue(
                    issue_id="ISS-004",
                    pregunta="¿Existe coherencia con el marco comunitario (Directivas InfoSoc, DSM) y la ley nacional?",
                    encaje_ref="Directiva 2001/29/CE; Directiva 2019/790 (DSM)",
                    principio="primacía del derecho UE / armonización",
                    evidencias_requeridas=["Transposición nacional aplicable", "Excepciones y limitaciones"],
                    alternativa="Incluir puente jurisdiccional explícito indicando ley nacional aplicable",
                )
            )
        elif jurisdiction == Jurisdiction.US:
            issues.append(
                Issue(
                    issue_id="ISS-004",
                    pregunta="¿Cumple la cláusula con los requisitos del Copyright Act (17 USC)?",
                    encaje_ref="17 USC §§ 101, 106, 201-205, 302",
                    principio="statutory compliance / work-for-hire doctrine",
                    evidencias_requeridas=["Signed writing", "Specification of rights", "Duration"],
                    alternativa="Explicit specification of exclusive rights per § 106; signed instrument per § 204",
                )
            )
        else:
            issues.append(
                Issue(
                    issue_id="ISS-004",
                    pregunta="¿Qué ley aplicable rige y existen conflictos jurisdiccionales?",
                    encaje_ref="Berna art. 5(2); Roma I art. 4",
                    principio="lex loci protectionis / autonomía de la voluntad",
                    evidencias_requeridas=["Cláusula de ley aplicable", "Análisis de conexión más estrecha"],
                    alternativa="Incluir cláusula de ley aplicable y foro competente",
                )
            )

    return issues[:4]


def _build_issues_llm(
    clause: str,
    jurisdiction: Jurisdiction,
    instrument_type: str,
    risks: List[RiskFlag],
) -> List[Issue]:
    """LLM-powered issue decomposition (wraps legacy decompose_clause)."""
    if _legacy_decompose is None:
        return _build_issues_heuristic(clause, jurisdiction, instrument_type, risks)

    try:
        raw_nodes = _legacy_decompose(clause, jurisdiction.value)
        issues = []
        for i, node in enumerate(raw_nodes[:4]):
            issues.append(
                Issue(
                    issue_id=f"ISS-{i+1:03d}",
                    pregunta=node.get("pregunta", ""),
                    encaje_ref=node.get("encaje_ref", ""),
                    principio=node.get("principio", ""),
                    evidencias_requeridas=node.get("evidencias_requeridas", []),
                    alternativa=node.get("alternativa", ""),
                )
            )
        return issues if issues else _build_issues_heuristic(clause, jurisdiction, instrument_type, risks)
    except Exception:
        return _build_issues_heuristic(clause, jurisdiction, instrument_type, risks)


class InquiryEngineAgent(BaseAgent[InquiryEngineInput, InquiryEngineOutput]):
    @property
    def name(self) -> str:
        return "inquiry-engine"

    def execute(self, inp: InquiryEngineInput) -> InquiryEngineOutput:
        risks = _detect_risks(inp.clause)

        use_llm = os.getenv("USE_LLM", "0") == "1"
        if use_llm:
            issues = _build_issues_llm(inp.clause, inp.jurisdiction, inp.instrument_type, risks)
        else:
            issues = _build_issues_heuristic(inp.clause, inp.jurisdiction, inp.instrument_type, risks)

        # GUARDRAIL: enforce max 4 issues
        issues = issues[:4]

        return InquiryEngineOutput(
            issues=issues,
            risk_flags=risks,
            instrument_type=inp.instrument_type,
        )
