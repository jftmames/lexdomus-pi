from typing import List, Dict, Any
import yaml
from pathlib import Path
from .retriever import retrieve_candidates, policy_filter

POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"

def load_policy() -> Dict[str, Any]:
    return yaml.safe_load(POLICY_PATH.read_text())

def source_required_answer(question: str, k: int = 8) -> Dict[str, Any]:
    policy = load_policy()
    cands = retrieve_candidates(question, k=max(k, policy["rag"]["retrieval"]["top_k"]))
    # Filtra por policy
    cands = [c for c in cands if policy_filter(c.get("meta", {}), policy)]
    if len(cands) < policy["rag"]["thresholds"]["min_citations"]:
        return {
            "status": "NO_CONCLUYENTE",
            "missing": "Evidencia insuficiente para citar con pinpoint",
            "candidates": cands
        }
    # Marca 'pinpoint' si meta.ref == 'pinpoint'
    for c in cands:
        c["meta"]["pinpoint"] = bool(c["meta"].get("ref") == "pinpoint")
    return {
        "status": "OK",
        "citations": cands
    }
