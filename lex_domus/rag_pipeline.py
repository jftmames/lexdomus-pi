from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from .contracts import source_is_allowed

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
    return source_is_allowed(policy, meta)

def source_required_answer(question: str,
                           jurisdiction: Optional[str] = None,
                           policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Recupera citas y aplica política. Firma flexible: admite 'jurisdiction' opcional.
    """
    policy = load_policy() if policy is None else policy
    from .retriever import retrieve_candidates
    cands = retrieve_candidates(question, k=6, policy=policy)

    filtered = [c for c in cands if _allowed(policy, c.get("meta", {}))]
    status = "OK" if filtered else "NO_EVIDENCE"
    return {"status": status, "citations": filtered}
