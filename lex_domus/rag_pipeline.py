from typing import List, Dict, Any
import yaml
from pathlib import Path
from .retriever import retrieve_candidates, policy_filter

POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"

def load_policy() -> Dict[str, Any]:
    return yaml.safe_load(POLICY_PATH.read_text())

def source_required_answer(question: str, k: int = 8) -> Dict[str, Any]:
    policy = load_policy()
    cands = retrieve_candidates(question, k=k)
    cands = [c for c in cands if policy_filter(c.get('meta', {}), policy)]
    if not cands or len(cands) < policy['rag']['thresholds']['min_citations']:
        return {"status": "NO_CONCLUYENTE", "missing": "Evidencia insuficiente para citar con pinpoint"}
    # TODO: construir respuesta con fragmentos citables
    return {"status": "OK", "citations": cands[:policy['rag']['thresholds']['min_citations']]}
