# app/pipeline.py — versión robusta para Streamlit/Actions
from pathlib import Path
import sys, os

# Asegura que la raíz del repo esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def analyze_clause(clause: str, jurisdiction: str):
    """
    Orquesta el análisis: Inquiry -> RAG -> Flags -> Gate -> Opinión -> Alternativa -> EEE.
    Importa dependencias LAZY (dentro de la función) para no romper la carga del módulo.
    """
    # --- Imports perezosos + fallbacks seguros ---
    try:
        from verdiktia.inquiry_engine import decompose_clause
    except Exception:
        decompose_clause = None

    # RAG + Policy
    try:
        from lex_domus.rag_pipeline import source_required_answer, load_policy
    except Exception:
        # Fallbacks si no carga lex_domus.rag_pipeline
        def _safe_load_policy():
            policy_path = ROOT / "policies" / "policy.yaml"
            try:
                import yaml  # type: ignore
                if policy_path.exists():
                    return yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            except Exception:
                pass
            # Política mínima por defecto
            return {
                "sources": {"allowed": ["BOE", "EUR-Lex", "WIPO", "USC"]},
                "privacy": {"block_biometrics": True},
            }

        def _safe_sra(question: str, jurisdiction: str, policy: dict):
            # Intenta al menos recuperar candidatos vía retriever si existe
            try:
                from lex_domus.retriever import retrieve_candidates  # type: ignore
                cands = retrieve_candidates(question, k=4) or []
            except Exception:
                cands = []
            status = "OK" if cands else "NO_EVIDENCE"
            return {"status": status, "citations": cands}

        load_policy = _safe_load_policy
        source_required_answer = _safe_sra

    # Flags + alternativa
    try:
        from lex_domus.flagger import detect_flags, propose_alternative
    except Exception:
        def detect_flags(_clause, _jur, _per_node): return []
        def propose_alternative(_clause, _jur, _flags): return ""

    # EEE (scoring)
    try:
        from metrics_eee.scorer import score_eee
    except Exception:
        def score_eee(**_kwargs): return {"T": 0.0, "J": 0.0, "P": 0.0}

    # Logging de trazabilidad (opcional)
    try:
        from metrics_eee.logger import append_log
    except Exception:
        def append_log(**_kwargs): return None

    # Redacción LLM (o MOCK)
    try:
        from app.writer_llm import draft_opinion_llm
    except Exception:
        def draft_opinion_llm(_clause, _jur, _per_node, _flags):
            return {
                "analysis_md": "*LLM no disponible (modo MOCK)*",
                "pros": [],
                "cons": [],
                "devils_advocate": {},
            }

    # --- Policy ---
    policy = load_policy()

    # --- Inquiry (descomposición) ---
    if callable(decompose_clause):
        try:
            nodes = decompose_clause(clause, jurisdiction)
        except Exception:
            nodes = [{"title": "Cláusula", "question": "Validez y alcance", "jurisdiction": jurisdiction}]
    else:
        nodes = [{"title": "Cláusula", "question": "Validez y alcance", "jurisdiction": jurisdiction}]

    # --- RAG por nodo ---
    per_node = []
    for node in nodes:
        q = node.get("question") if isinstance(node, dict) else str(node)
        retr = source_required_answer(q, jurisdiction=jurisdiction, policy=policy)
        per_node.append({"node": node, "retrieval": retr})

    # --- Flags + Gate ---
    flags = detect_flags(clause, jurisdiction, per_node) or []
    gate_status = "OK" if any(
        (it.get("retrieval", {}).get("status") == "OK" and it.get("retrieval", {}).get("citations"))
        for it in per_node
    ) else "NO_EVIDENCE"
    gate = {"status": gate_status}

    # --- Opinión LLM / MOCK ---
    opinion = draft_opinion_llm(clause, jurisdiction, per_node, flags) or {}
    # sanea estructura mínima
    if "analysis_md" not in opinion and "analysis" in opinion:
        opinion["analysis_md"] = opinion.get("analysis")

    # --- Cláusula alternativa ---
    alternative = propose_alternative(clause, jurisdiction, flags) or ""

    # --- EEE ---
    eee = score_eee(per_node=per_node, flags=flags, gate=gate)

    result = {
        "engine": "LLM" if os.getenv("USE_LLM", "0") == "1" else "MOCK",
        "per_node": per_node,
        "flags": flags,
        "gate": gate,
        "opinion": opinion,
        "alternative_clause": alternative,
        "EEE": eee,
    }

    try:
        append_log(clause=clause, jurisdiction=jurisdiction, result=result)
    except Exception:
        pass

    return result


