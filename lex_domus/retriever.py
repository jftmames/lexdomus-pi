from pathlib import Path
from typing import List, Dict, Any, Optional
import json, re
from .contracts import Citation, citation_from_record, source_is_allowed

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "docs_chunks" / "chunks.jsonl"

_WORD = re.compile(r"\w+", re.U)

def _tok(s: str) -> set:
    return set(_WORD.findall((s or "").lower()))

def _score(query_tokens: set, text: str) -> int:
    if not text:
        return 0
    return len(query_tokens & _tok(text))

def retrieve_candidates(query: str, k: int = 6, *,
                        policy: Optional[Dict[str, Any]] = None) -> List[Citation]:
    """
    Recuperación léxica sobre chunks.jsonl, con procedencia bajo 'meta'.
    Si se proporciona política, se aplica antes del límite de candidatos.
    """
    if not isinstance(query, str):
        raise ValueError("Retrieval query must be a string")
    if not query.strip() or k <= 0 or not CHUNKS.exists():
        return []

    q_tokens = _tok(query)
    scored: List[Dict[str, Any]] = []
    with CHUNKS.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            citation = citation_from_record(rec)
            if citation is None:
                continue
            if policy is not None and not source_is_allowed(policy, citation["meta"]):
                continue
            sc = _score(q_tokens, citation["text"])
            if sc > 0:
                scored.append({**citation, "_score": sc})

    scored.sort(key=lambda r: r.get("_score", 0), reverse=True)
    top = scored[:k]
    for r in top:
        r.pop("_score", None)
    return top
