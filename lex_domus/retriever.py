"""Lexical retrieval over a single verified in-memory corpus snapshot."""
from typing import List, Dict, Any, Optional

from .contracts import Citation
from .policy import validate_policy
from .snapshots import VerifiedSnapshot, load_active_snapshot


def retrieve_candidates(query: str, k: int = 6, *,
                        policy: Optional[Dict[str, Any]] = None,
                        snapshot: Optional[VerifiedSnapshot] = None) -> List[Citation]:
    if policy is None:
        from .rag_pipeline import load_policy
        policy = load_policy()
    validate_policy(policy)
    snapshot = load_active_snapshot(policy) if snapshot is None else snapshot
    return snapshot.search(query, k, policy)
