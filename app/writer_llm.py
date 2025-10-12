import os, json
from typing import Dict, Any, List
from llm.provider import call_llm_json

def _schema() -> Dict[str, Any]:
    return {
        "name": "OpinionSchema",
        "schema": {
            "type": "object",
            "properties": {
                "analysis_md": {"type": "string"},
                "pros": {"type": "array", "items": {"type": "string"}},
                "cons": {"type": "array", "items": {"type": "string"}},
                "devils_advocate": {
                    "type": "object",
                    "properties": {
                        "hipotesis": {"type": "string"},
                        "lectura": {"type": "string"},
                        "cuando_mejor": {"type": "string"}
                    },
                    "required": ["hipotesis","lectura","cuando_mejor"],
                    "additionalProperties": False
                }
            },
            "required": ["analysis_md","pros","cons","devils_advocate"],
            "additionalProperties": False
        }
    }

def draft_opinion_llm(clause: str, jurisdiction: str, per_node: List[Dict[str, Any]], flags: List[str]) -> Dict[str, Any]:
    # Enforce "source-required": si no hay suficientes citas, devolvemos “No concluyente”.
    citations: List[Dict[str, Any]] = []
    for item in per_node:
        retr = item["retrieval"]
        node = item["node"]
        if retr["status"] == "OK":
            for c in retr.get("citations", [])[:2]:
                citations.append({
                    "pregunta": node["pregunta"],
                    "meta": c["meta"],
                    "texto": c["text"][:900]
                })

    if len(citations) < 2:
        return {
            "analysis_md": "### Análisis\nNo concluyente: faltan citas con pinpoint suficientes.",
            "pros": [],
            "cons": [],
            "devils_advocate": {"hipotesis":"—","lectura":"—","cuando_mejor":"—"}
        }

    system = (
        "Eres un asistente jurídico especializado en Propiedad Intelectual. "
        "Redacta un dictamen breve y preciso SOLO con las evidencias proporcionadas. "
        "Prohíbe introducir normas no citadas. Devuelve EXCLUSIVAMENTE JSON del esquema."
    )

    payload = {
        "instrucciones": (
            "Estructura las secciones así: "
            "1) 'analysis_md' con bullets 'regla→hechos→aplicación' y citas claras; "
            "2) 'pros' y 'cons'; "
            "3) 'devils_advocate' con hipótesis/lectura/condiciones."
        ),
        "jurisdiccion": jurisdiction,
        "clausula": clause,
        "flags": flags,
        "citas": citations,
        "reglas": {
            "source_required": True,
            "si_insuficiente": "No concluyente"
        }
    }

    return call_llm_json(system, payload, _schema())
