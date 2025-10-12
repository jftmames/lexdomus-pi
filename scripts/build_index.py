import os, json, pickle, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "docs_chunks" / "chunks.jsonl"
INDICES = ROOT / "indices"
INDICES.mkdir(parents=True, exist_ok=True)

# ---- BM25 ----
from rank_bm25 import BM25Okapi

def build_bm25():
    docs, metas = [], []
    with open(CHUNKS, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            docs.append(rec["text"])
            metas.append(rec)
    tokenized = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized)
    with open(INDICES / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized, "metas": metas}, f)
    print("BM25 index listo.")

# ---- FAISS (opcional, híbrido) ----
def build_faiss():
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except Exception as e:
        print("FAISS/embeddings no disponibles en este entorno. Solo BM25.")
        return

    texts, metas = [], []
    with open(CHUNKS, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            texts.append(rec["text"])
            metas.append(rec)

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    X = model.encode(texts, normalize_embeddings=True, show_progress_bar=False).astype("float32")
    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)
    faiss.write_index(index, str(INDICES / "faiss.index"))
    np.save(INDICES / "embeddings.npy", X)
    with open(INDICES / "vector_meta.json", "w", encoding="utf-8") as f:
        json.dump({"metas": metas}, f, ensure_ascii=False)
    print("FAISS index listo.")

if __name__ == "__main__":
    build_bm25()
    build_faiss()
