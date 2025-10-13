from pathlib import Path
from typing import List, Dict, Any, Optional
import json

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policies" / "policy.yaml"

def load_policy() -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
        if POLICY_PATH.exists():
            return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    # Política mínima por defecto
    return {"sources": {"allowed": ["BOE", "EUR-Lex", "WIPO", "USC"]}}

def _allowed(policy: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    allow = set((policy.get("sources", {}) or {}).get("allowed", []))
    if not allow:
        return True
    src = (meta or {}).get("source", "")
    return (src in allow) if src else True

def source_required_answer(question: str,
                           jurisdiction: Optional[str] = None,
                           policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Recupera citas y aplica política. Firma flexible: admite 'jurisdiction' opcional.
    """
    policy = policy or load_policy()
    try:
        from .retriever import retrieve_candidates
        cands = retrieve_candidates(question, k=6) or []
    except Exception:
        cands = []

    filtered = [c for c in cands if _allowed(policy, c.get("meta", {}))]
    status = "OK" if filtered else "NO_EVIDENCE"
    return {"status": status, "citations": filtered}

