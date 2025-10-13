import os
from typing import Dict, Any

def passes_thresholds(eee: Dict[str, float], policy: Dict[str, Any]) -> bool:
    th = policy.get("eee_gate", {})
    return (
        eee.get("T", 0) >= th.get("min_T", 4.5) and
        eee.get("J", 0) >= th.get("min_J", 4.0) and
        eee.get("P", 0) >= th.get("min_P", 4.0)
    )

def apply_gate(result: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Si no pasa umbrales EEE o no hay citas suficientes, marca 'NO_CONCLUYENTE'
    y expone qué falta. No reescribe con LLM (mantiene disciplina 'source-required').
    """
    eee = result.get("EEE", {})
    min_cites = policy["rag"]["thresholds"]["min_citations"]
    have_cites = 0
    for item in result.get("per_node", []):
        retr = item["retrieval"]
        if retr.get("status") == "OK":
            have_cites += len(retr.get("citations", []))

    ok = passes_thresholds(eee, policy) and have_cites >= min_cites
    result["gate"] = {
        "status": "OK" if ok else "NO_CONCLUYENTE",
        "reason": None if ok else f"EEE/T o evidencia insuficiente (citas totales={have_cites}, min={min_cites})"
    }
    return result
