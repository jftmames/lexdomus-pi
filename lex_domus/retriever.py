from pathlib import Path
from typing import List, Dict, Any
import json, re

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "docs_chunks" / "chunks.jsonl"

_WORD = re.compile(r"\w+", re.U)

def _tok(s: str) -> set:
    return set(_WORD.findall((s or "").lower()))

def _score(query_tokens: set, text: str) -> int:
    if not text:
        return 0
    return len(query_tokens & _tok(text))

def retrieve_candidates(query: str, k: int = 6) -> List[Dict[str, Any]]:
    """
    Fallback universal: si no hay FAISS/BM25 disponibles,
    escanea chunks.jsonl y puntúa por solapamiento de tokens.
    Devuelve una lista de citas estilo {'text':..., 'meta':{...}}.
    """
    if not CHUNKS.exists():
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
            text = rec.get("text", "")
            meta = rec.get("meta", {})
            sc = _score(q_tokens, text)
            if sc > 0:
                scored.append({"text": text, "meta": meta, "_score": sc})

    scored.sort(key=lambda r: r.get("_score", 0), reverse=True)
    top = scored[:k]
    for r in top:
        r.pop("_score", None)
    return top

