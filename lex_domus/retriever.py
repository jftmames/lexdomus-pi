from typing import List, Dict, Any, Tuple
import json, pickle, pathlib
from rapidfuzz import fuzz

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDICES = ROOT / "indices"

# Carga BM25
with open(INDICES / "bm25.pkl", "rb") as f:
    bm25_pack = pickle.load(f)
bm25 = bm25_pack["bm25"]
tokenized = bm25_pack["tokenized"]
metas = bm25_pack["metas"]

# Intenta FAISS + embeddings
try:
    import faiss, numpy as np
    from sentence_transformers import SentenceTransformer, CrossEncoder
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    X = np.load(INDICES / "embeddings.npy")
    faiss_index = faiss.read_index(str(INDICES / "faiss.index"))
except Exception:
    model, X, faiss_index = None, None, None

# Cross-encoder (reranker denso) — fallback a None si no disponible
try:
    from sentence_transformers import CrossEncoder
    CE = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
except Exception:
    CE = None

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
    scores = {}
    for i,s in bm: scores[i] = scores.get(i, 0.0) + alpha*s
    for i,s in dn: scores[i] = scores.get(i, 0.0) + (1-alpha)*s
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def _rerank_ce(query: str, cand_ids: List[int], top_rerank=32) -> List[int]:
    # Cross-encoder si está disponible
    if CE is not None:
        pairs = [[query, metas[i]["text"]] for i in cand_ids[:top_rerank]]
        scores = CE.predict(pairs).tolist()
        order = sorted(list(zip(cand_ids[:top_rerank], scores)), key=lambda x: x[1], reverse=True)
        return [i for i,_ in order] + cand_ids[top_rerank:]
    # Fallback: similitud textual
    scored = []
    for idx in cand_ids[:top_rerank]:
        scored.append((idx, fuzz.token_set_ratio(query, metas[idx]["text"])))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [i for i,_ in scored] + cand_ids[top_rerank:]

def retrieve_candidates(query: str, k: int = 8) -> List[Dict[str, Any]]:
    bm = _bm25_scores(query, max(k*6, 30))
    dn = _faiss_scores(query, max(k*6, 30))
    merged = _merge_scores(bm, dn, alpha=0.7)
    ranked_ids = [i for i,_ in merged]
    reranked = _rerank_ce(query, ranked_ids, top_rerank=32)

    out = []
    for idx in reranked[:k]:
        m = metas[idx]
        out.append({
            "meta": {
                "doc_id": m["doc_id"],
                "source": m["source"],
                "jurisdiction": m["jurisdiction"],
                "title": m["title"],
                "url": m.get("url",""),
                "ref": m.get("ref",""),
                "pinpoint": bool(m.get("pinpoint", False)),
                "line_start": m.get("line_start"),
                "line_end": m.get("line_end"),
            },
            "text": m["text"]
        })
    return out
