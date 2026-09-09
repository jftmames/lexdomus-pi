# api/main.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from time import perf_counter
from pathlib import Path
from uuid import uuid4
import logging
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Carga pipeline de tu MVP
from app.pipeline import analyze_clause
from api.schemas import AnalyzeIn, AnalyzeResponse, ErrorResponse, InputIssue
from lex_domus.policy import PolicyError

logger = logging.getLogger(__name__)

# Opcional: MCP health si está presente
try:
    from mcp.registry import health as mcp_health, list_connectors
    HAS_MCP = True
except Exception:
    HAS_MCP = False

app = FastAPI(title="LexDomus-PI API", version="1.1.0")


def request_identifier(request: Request):
    if not hasattr(request.state, "request_id"):
        request.state.request_id = uuid4()
    return request.state.request_id


def error_response(request: Request, http_status: int, status: str, message: str, errors=None):
    body = ErrorResponse(request_id=request_identifier(request), status=status,
                         message=message, errors=errors or [])
    return JSONResponse(status_code=http_status, content=body.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Never return Pydantic's input, arbitrary location keys or exception text.
    issues = []
    codes = {"missing": "required", "string_type": "invalid_type",
             "string_too_short": "empty", "string_too_long": "too_long",
             "literal_error": "unsupported_value", "extra_forbidden": "unexpected_field",
             "json_invalid": "invalid_json", "value_error": "invalid_value"}
    for error in exc.errors():
        loc = error.get("loc", ())
        field = loc[1] if len(loc) == 2 and loc[0] == "body" and loc[1] in ("clause", "jurisdiction") else "body"
        issue = InputIssue(field=field, code=codes.get(error.get("type"), "invalid_value"))
        if issue not in issues:
            issues.append(issue)
    body = exc.body
    out_of_scope = (isinstance(body, dict) and isinstance(body.get("jurisdiction"), str)
                    and body["jurisdiction"] != "ES")
    if out_of_scope:
        return error_response(request, 422, "OUT_OF_SCOPE",
                              "El piloto sólo admite el ámbito español (ES).", issues)
    return error_response(request, 422, "INVALID_INPUT",
                          "Revisa el formato, el contenido y el límite de 5.000 caracteres.", issues)


@app.exception_handler(StarletteHTTPException)
async def invalid_http_body(request: Request, exc: StarletteHTTPException):
    if request.url.path == "/analyze" and exc.status_code == 400:
        return error_response(request, 400, "INVALID_INPUT", "No se pudo interpretar el cuerpo JSON.",
                              [InputIssue(field="body", code="invalid_json")])
    return await http_exception_handler(request, exc)

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

@app.post("/analyze", response_model=AnalyzeResponse,
          responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
                     500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def analyze(body: AnalyzeIn, request: Request):
    t0 = perf_counter()
    request_id = request_identifier(request)
    try:
        res = analyze_clause(body.clause, body.jurisdiction)
        no_evidence = res["gate"]["status"] == "NO_EVIDENCE"
        payload = dict(res)
        if no_evidence:
            # The pipeline must abstain before generation. Normalize empty legacy
            # containers here; do not mask a substantive contradictory result.
            if payload.get("opinion") in ({}, None):
                payload["opinion"] = None
            if payload.get("alternative_clause") in ("", None):
                payload["alternative_clause"] = None
        payload.update(
            request_id=request_id,
            status="INSUFFICIENT_EVIDENCE" if no_evidence else "DRAFT_REVIEW_REQUIRED",
            message=("No se ha recuperado evidencia admisible para preparar el borrador."
                     if no_evidence else "Borrador pendiente de revisión profesional."),
            review_required=True,
            latency_ms=round((perf_counter() - t0) * 1000.0, 2),
        )
        validated = AnalyzeResponse.model_validate(payload)
        # Validate AND serialize within the error boundary (including invalid
        # Unicode/nonfinite output); no raw exception is exposed to clients.
        return JSONResponse(content=validated.model_dump(mode="json"))
    except PolicyError:
        logger.warning("Analysis unavailable request_id=%s type=PolicyError", request_id)
        return error_response(request, 503, "TECHNICAL_ERROR",
                              "Análisis no disponible: la política de fuentes requiere revisión del responsable.")
    except Exception as exc:
        logger.error("Analysis failed request_id=%s type=%s", request_id, type(exc).__name__)
        return error_response(request, 500, "TECHNICAL_ERROR",
                              "No se pudo completar el análisis. Conserva el identificador de la petición.")
