# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from time import perf_counter
from pathlib import Path
import sys, os

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Carga pipeline de tu MVP
from app.pipeline import analyze_clause

# Opcional: MCP health si está presente
try:
    from mcp.registry import health as mcp_health, list_connectors
    HAS_MCP = True
except Exception:
    HAS_MCP = False

class AnalyzeIn(BaseModel):
    clause: str
    jurisdiction: str

app = FastAPI(title="LexDomus-PI API", version="1.0.0")

# CORS abierto para demos (restringe en prod con NEXT_PUBLIC_WEB_ORIGIN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NUEVA RUTA PARA CORREGIR EL 404 EN LA HOME ---
@app.get("/")
def read_root():
    return {"message": "LexDomus API is running. Go to /docs for Swagger UI."}
# --------------------------------------------------

@app.get("/health")
def health():
    data = {
        "status": "ok",
        "has_mcp": HAS_MCP,
        "connectors": list_connectors() if HAS_MCP else {},
        "indices": {
            "chunks": (ROOT / "data" / "docs_chunks" / "chunks.jsonl").exists(),
            "faiss": (ROOT / "indices" / "faiss.index").exists(),
            "bm25": (ROOT / "indices" / "bm25.pkl").exists(),
        },
    }
    if HAS_MCP:
        try:
            data["mcp_corpus"] = mcp_health("corpus")
        except Exception:
            pass
    return data

@app.post("/analyze")
def analyze(body: AnalyzeIn):
    t0 = perf_counter()
    try:
        res = analyze_clause(body.clause, body.jurisdiction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    res["latency_ms"] = round((perf_counter() - t0) * 1000.0, 2)
    return res
