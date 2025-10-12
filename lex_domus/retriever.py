from typing import List, Dict, Any, Tuple
import json, pickle, pathlib
from rapidfuzz import fuzz

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDICES = ROOT / "indices"
CHUNKS = ROOT / "data" / "docs_chunks" / "chunks.jsonl"

# Carga BM25
with open(INDICES / "bm25.pkl", "rb") as f:
    bm25_pack = pickle.load(f)
bm25 = bm25_pack["bm25"]
tokenized = bm25_pack["tokenized"]
metas = bm25_pack["metas"]

# Intenta cargar FAISS
try:
    import faiss, numpy as np
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    X = np.load(INDICES / "embeddings.npy")
    faiss_index = faiss.read_index(str(INDICES / "faiss.index"))
except Exception:
    model, X, faiss_index = None, None, None

def policy_filter(doc_meta: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    allowed = policy["sources"]["allowed"]
    src_ok = any(allow in doc_meta.get("source","") for allow in allowed)
    if not src_ok:
        return False
    if policy["privacy"]["block_biometrics"] and doc_meta.get("contains_faces", False):
        return False
    return True

def _bm25_scores(query: str, k: int) -> List[Tuple[int, float]]:
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
    return ranked

def _faiss_scores(query: str, k: int) -> List[Tuple[int, float]]:
    if model is None or faiss_index is None:
        return []
    q = model.encode([query], normalize_embeddings=True).astype("float32")
    D, I = faiss_index.search(q, k)
    return list(zip(I[0].tolist(), D[0].tolist()))

def _merge_scores(bm: List[Tuple[int,float]], dn: List[Tuple[int,float]], alpha=0.6) -> List[Tuple[int,float]]:
    # fusiones por doc_id con ponderación
    scores = {}
    for i,s in bm:
        scores[i] = scores.get(i, 0.0) + alpha*s
    for i,s in dn:
        scores[i] = scores.get(i, 0.0) + (1-alpha)*s
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def _rerank(query: str, candidates: List[int], top_rerank=10) -> List[int]:
    # Rerank ligero por similitud textual (sin cross-encoder)
    scored = []
    for idx in candidates[:top_rerank]:
        txt = metas[idx]["text"]
        scored.append((idx, fuzz.token_set_ratio(query, txt)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [i for i,_ in scored] + candidates[top_rerank:]

def retrieve_candidates(query: str, k: int = 8) -> List[Dict[str, Any]]:
    bm = _bm25_scores(query, max(k*5, 20))
    dn = _faiss_scores(query, max(k*5, 20))
    merged = _merge_scores(bm, dn, alpha=0.7)
    ranked_ids = [i for i,_ in merged]
    reranked = _rerank(query, ranked_ids, top_rerank=15)
    out = []
    for idx in reranked[:k]:
        m = metas[idx]
        out.append({
            "meta": {
                "doc_id": m["doc_id"],
                "source": m["source"],
                "jurisdiction": m["jurisdiction"],
                "title": m["title"],
                "ref": m.get("ref","")
            },
            "text": m["text"]
        })
    return out
