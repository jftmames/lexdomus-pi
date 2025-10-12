from typing import List, Dict, Any
import yaml
from pathlib import Path
from .retriever import retrieve_candidates, policy_filter

POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"

# --- Política por defecto (fallback) si no existe policies/policy.yaml ---
DEFAULT_POLICY: Dict[str, Any] = {
    "sources": {
        "allowed": ["BOE", "EUR-Lex", "WIPO/OMPI", "USC (Cornell/LII)"],
        "denied": ["wikis no oficiales", "blogs sin revisión", "datasets con imágenes personales"],
    },
    "privacy": {
        "block_personal_data": True,
        "block_biometrics": True,
        "pre_index_filters": ["faces", "signatures", "emails", "phones", "addresses"],
        "pre_prompt_sanitization": True,
        "deny_on_privacy_violation": True,
    },
    "rag": {
        "retrieval": {
            "top_k": 8,
            "hybrid": True,
            "hyde": True,
            "rerank": "cross-encoder",
        },
        "thresholds": {
            "min_citations": 2,
            "require_pinpoint": True,
        },
        "generation": {
            "source_required": True,
            "max_context_chars": 12000,
        },
    },
    "eee_gate": {
        "min_T": 4.5,
        "min_J": 4.0,
        "min_P": 4.0,
        "enforce_no_conclusion_if_insufficient": True,
        "penalize_vague_citations": True,
    },
}

def load_policy() -> Dict[str, Any]:
    """Carga policy.yaml; si no existe, usa DEFAULT_POLICY."""
    try:
        return yaml.safe_load(POLICY_PATH.read_text())
    except FileNotFoundError:
        return DEFAULT_POLICY

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
    # Marca 'pinpoint' si la meta lo indica
    for c in cands:
        c["meta"]["pinpoint"] = bool(c["meta"].get("ref") == "pinpoint")
    return {
        "status": "OK",
        "citations": cands
    }
