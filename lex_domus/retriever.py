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

# Intenta cargar FAISS + encoder denso
try:
    import faiss, numpy as np
    from sentence_transformers import SentenceTransformer, CrossEncoder
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    X = np.load(INDICES / "embeddings.npy")
    faiss_index = faiss.read_index(str(INDICES / "faiss.index"))
except Exception:
    model, X, faiss_index = None, None, None

# Cross-encoder (reranker)
try:
    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
except Exception:
    cross_encoder = None

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

def _merge_scores(bm: List[Tuple[int,float]], dn: List[Tuple[int,float]], alpha=0.7) -> List[int]:
    scores = {}
    for i,s in bm:
        scores[i] = scores.get(i, 0.0) + alpha*s
    for i,s in dn:
        scores[i] = scores.get(i, 0.0) + (1-alpha)*s
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [i for i,_ in ranked]

def _rerank(query: str, idxs: List[int], top_rerank=15) -> List[int]:
    # Si hay cross-encoder, úsalo en los primeros 'top_rerank'
    if cross_encoder is not None and idxs:
        pairs = [(query, metas[i]["text"]) for i in idxs[:top_rerank]]
        scores = cross_encoder.predict(pairs).tolist()
        scored = list(zip(idxs[:top_rerank], scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [i for i,_ in scored] + idxs[top_rerank:]
    # Fallback: similitud rápida
    scored = []
    for i in idxs[:top_rerank]:
        scored.append((i, fuzz.token_set_ratio(query, metas[i]["text"])))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [i for i,_ in scored] + idxs[top_rerank:]

def retrieve_candidates(query: str, k: int = 8) -> List[Dict[str, Any]]:
    bm = _bm25_scores(query, max(k*5, 20))
    dn = _faiss_scores(query, max(k*5, 20))
    merged_ids = _merge_scores(bm, dn, alpha=0.7)
    reranked = _rerank(query, merged_ids, top_rerank=20)
    out = []
    for idx in reranked[:k]:
        m = metas[idx]
        out.append({
            "meta": {
                "doc_id": m["doc_id"],
                "source": m["source"],
                "jurisdiction": m["jurisdiction"],
                "title": m["title"],
                "family": m.get("family",""),
                "ref_label": m.get("ref_label",""),
                "ref_url": m.get("ref_url",""),
                "pinpoint": bool(m.get("pinpoint", False)),
                "line_start": m.get("line_start"),
                "line_end": m.get("line_end"),
            },
            "text": m["text"]
        })
    return out
