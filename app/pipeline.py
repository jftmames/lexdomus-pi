# app/pipeline.py — robusto para firmas variadas (SRA, flags, alt, EEE) y entornos Streamlit/Actions
from pathlib import Path
import sys, os

# Asegura que la raíz del repo esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def analyze_clause(clause: str, jurisdiction: str):
    """
    Orquesta el análisis: Inquiry -> RAG -> Flags -> Gate -> Opinión -> Alternativa -> EEE.
    Imports perezosos y dispatchers para soportar firmas distintas.
    """
    # --- Imports perezosos + fallbacks seguros ---
    try:
        from verdiktia.inquiry_engine import decompose_clause
    except Exception:
        decompose_clause = None

    # RAG + Policy
    try:
        from lex_domus.rag_pipeline import (
            source_required_answer as _sra_real,
            load_policy as _load_policy_real,
        )
    except Exception:
        _sra_real = None
        _load_policy_real = None

    # Flags + alternativa (firmas variables según repo)
    try:
        from lex_domus.flagger import detect_flags as _df_real, propose_alternative as _pa_real
    except Exception:
        _df_real = None
        _pa_real = None

    # EEE (scoring) — firma variable
    try:
        from metrics_eee.scorer import score_eee as _eee_real
    except Exception:
        _eee_real = None

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

    # --- Helpers: load_policy & fallbacks SRA/flags/alt/EEE ---
    def _safe_load_policy():
        if _load_policy_real:
            try:
                return _load_policy_real()
            except Exception:
                pass
        try:
            import yaml  # type: ignore
            policy_path = ROOT / "policies" / "policy.yaml"
            if policy_path.exists():
                return yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {
            "sources": {"allowed": ["BOE", "EUR-Lex", "WIPO", "USC"]},
            "privacy": {"block_biometrics": True},
        }

    def _safe_sra(question: str, jurisdiction: str, policy: dict):
        try:
            from lex_domus.retriever import retrieve_candidates  # type: ignore
            cands = retrieve_candidates(question, k=4) or []
        except Exception:
            cands = []
        status = "OK" if cands else "NO_EVIDENCE"
        return {"status": status, "citations": cands}

    def _safe_detect_flags(_clause, _jur=None, _per_node=None):
        return []

    def _safe_propose_alt(_clause, _jur=None, _flags=None):
        return ""

    def _safe_eee(_per_node=None, _flags=None, _gate=None):
        return {"T": 0.0, "J": 0.0, "P": 0.0}

    # --- Normalizadores/dispatchers ---
    def _normalize_retrieval(ret):
        if ret is None:
            return {"status": "NO_EVIDENCE", "citations": []}
        if isinstance(ret, list):
            return {"status": "OK" if ret else "NO_EVIDENCE", "citations": ret}
        if isinstance(ret, dict):
            status = ret.get("status")
            cits = ret.get("citations")
            if isinstance(cits, list) and status:
                return {"status": status, "citations": cits}
            if "results" in ret and isinstance(ret["results"], list):
                return {"status": "OK" if ret["results"] else "NO_EVIDENCE", "citations": ret["results"]}
            inferred = ret.get("items") or ret.get("data") or []
            if not isinstance(inferred, list):
                inferred = []
            st = status or ("OK" if inferred else "NO_EVIDENCE")
            return {"status": st, "citations": inferred}
        return {"status": "NO_EVIDENCE", "citations": []}

    def _sra_dispatch(sra_fn, question: str, jurisdiction: str, policy: dict):
        if sra_fn is None:
            return _normalize_retrieval(_safe_sra(question, jurisdiction, policy))
        for call in (
            lambda: sra_fn(question, jurisdiction=jurisdiction, policy=policy),
            lambda: sra_fn(question, jurisdiction, policy),
            lambda: sra_fn(question, policy=policy),
            lambda: sra_fn(question, policy),
            lambda: sra_fn(question),
        ):
            try:
                return _normalize_retrieval(call())
            except TypeError:
                continue
            except Exception:
                continue
        return _normalize_retrieval(_safe_sra(question, jurisdiction, policy))

    def _flags_dispatch(df_fn, clause: str, jurisdiction: str, per_node):
        if df_fn is None:
            return _safe_detect_flags(clause, jurisdiction, per_node)
        for call in (
            lambda: df_fn(clause, jurisdiction, per_node),
            lambda: df_fn(clause, jurisdiction),
            lambda: df_fn(clause, per_node),
            lambda: df_fn(clause),
            lambda: df_fn(text=clause, jurisdiction=jurisdiction, per_node=per_node),
        ):
            try:
                ret = call()
                return ret or []
            except TypeError:
                continue
            except Exception:
                continue
        return _safe_detect_flags(clause, jurisdiction, per_node)

    def _alt_dispatch(pa_fn, clause: str, jurisdiction: str, flags):
        if pa_fn is None:
            return _safe_propose_alt(clause, jurisdiction, flags)
        for call in (
            lambda: pa_fn(clause, jurisdiction, flags),
            lambda: pa_fn(clause, flags),
            lambda: pa_fn(clause, jurisdiction),
            lambda: pa_fn(clause),
            lambda: pa_fn(text=clause, jurisdiction=jurisdiction, flags=flags),
        ):
            try:
                ret = call()
                return ret or ""
            except TypeError:
                continue
            except Exception:
                continue
        return _safe_propose_alt(clause, jurisdiction, flags)

    def _normalize_eee(ret):
        # Devuelve dict con T, J, P (floats)
        if isinstance(ret, dict):
            T = float(ret.get("T", 0) or 0)
            J = float(ret.get("J", 0) or 0)
            P = float(ret.get("P", 0) or 0)
            return {"T": T, "J": J, "P": P}
        if isinstance(ret, (list, tuple)) and len(ret) >= 3:
            try:
                return {"T": float(ret[0]), "J": float(ret[1]), "P": float(ret[2])}
            except Exception:
                return {"T": 0.0, "J": 0.0, "P": 0.0}
        if isinstance(ret, (int, float)):
            v = float(ret)
            return {"T": v, "J": v, "P": v}
        return {"T": 0.0, "J": 0.0, "P": 0.0}

    def _eee_dispatch(eee_fn, per_node, flags, gate):
        """
        Prueba, en orden:
          score_eee(per_node=..., flags=..., gate=...)
          score_eee(per_node, flags, gate)
          score_eee(per_node, flags)
          score_eee(per_node)
          score_eee({"per_node":..., "flags":..., "gate":...})
          score_eee()
        """
        if eee_fn is None:
            return _safe_eee(per_node, flags, gate)
        for call in (
            lambda: eee_fn(per_node=per_node, flags=flags, gate=gate),
            lambda: eee_fn(per_node, flags, gate),
            lambda: eee_fn(per_node, flags),
            lambda: eee_fn(per_node),
            lambda: eee_fn({"per_node": per_node, "flags": flags, "gate": gate}),
            lambda: eee_fn(),
        ):
            try:
                return _normalize_eee(call())
            except TypeError:
                continue
            except Exception:
                continue
        return _safe_eee(per_node, flags, gate)

    # --- Policy ---
    policy = _safe_load_policy()

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
        retr = _sra_dispatch(_sra_real, q, jurisdiction, policy)
        per_node.append({"node": node, "retrieval": retr})

    # --- Flags + Gate ---
    flags = _flags_dispatch(_df_real, clause, jurisdiction, per_node) or []
    gate_status = "OK" if any(
        (it.get("retrieval", {}).get("status") == "OK" and it.get("retrieval", {}).get("citations"))
        for it in per_node
    ) else "NO_EVIDENCE"
    gate = {"status": gate_status}

    # --- Opinión LLM / MOCK ---
    opinion = draft_opinion_llm(clause, jurisdiction, per_node, flags) or {}
    if "analysis_md" not in opinion and "analysis" in opinion:
        opinion["analysis_md"] = opinion.get("analysis")

    # --- Cláusula alternativa ---
    alternative = _alt_dispatch(_pa_real, clause, jurisdiction, flags) or ""

    # --- EEE (dispatcher robusto) ---
    score = _eee_dispatch(_eee_real, per_node, flags, gate)

    result = {
        "engine": "LLM" if os.getenv("USE_LLM", "0") == "1" else "MOCK",
        "per_node": per_node,
        "flags": flags,
        "gate": gate,
        "opinion": opinion,
        "alternative_clause": alternative,
        "EEE": score,
    }

    try:
        append_log(clause=clause, jurisdiction=jurisdiction, result=result)
    except Exception:
        pass

    return result

