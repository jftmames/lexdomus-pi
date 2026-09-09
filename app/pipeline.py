# app/pipeline.py — contratos explícitos para Inquiry/RAG; adaptadores legacy para flags/alt/EEE
from pathlib import Path
import sys, os

# Asegura que la raíz del repo esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def analyze_clause(clause: str, jurisdiction: str):
    """
    Orquesta el análisis: Inquiry -> RAG -> Flags -> Gate -> Opinión -> Alternativa -> EEE.
    Inquiry/RAG tienen firmas explícitas; flags, alternativa y EEE conservan adaptadores legacy.
    """
    # Inquiry and retrieval use explicit contracts; failures are not replaced.
    from verdiktia.inquiry_engine import decompose_clause

    # RAG has one contract: failures must not retry retrieval without policy.
    from lex_domus.rag_pipeline import source_required_answer, load_policy

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

    # --- Legacy fallbacks for flags/alternative/EEE (outside this change) ---
    def _safe_detect_flags(_clause, _jur=None, _per_node=None):
        return []

    def _safe_propose_alt(_clause, _jur=None, _flags=None):
        return ""

    def _safe_eee(_per_node=None, _flags=None, _gate=None):
        return {"T": 0.0, "J": 0.0, "P": 0.0}

    # --- Legacy dispatchers ---
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
    policy = load_policy()
    from lex_domus.policy import validate_policy
    validate_policy(policy, jurisdiction)

    # --- Inquiry (descomposición) ---
    nodes = decompose_clause(clause, jurisdiction)
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Inquiry must produce a nonempty list of nodes")

    # --- RAG por nodo (2 intentos: pregunta del nodo -> cláusula completa) ---
    per_node = []
    for node in nodes:
        q_base = node.get("pregunta") if isinstance(node, dict) else None
        if not isinstance(q_base, str) or not q_base.strip():
            raise ValueError("Inquiry node must contain a nonempty 'pregunta'")
        tries = [
            q_base,
            f"{q_base}\n\n[Texto de la cláusula]\n{clause}\n\n[Jurisdicción objetivo] {jurisdiction}",
        ]
        used_q = q_base
        retr = {"status": "NO_EVIDENCE", "citations": []}
        for q_try in tries:
            r = source_required_answer(q_try, jurisdiction=jurisdiction, policy=policy)
            # nos quedamos con el primer intento que traiga citas
            if r.get("status") == "OK" and r.get("citations"):
                retr = r
                used_q = q_try
                break
            # guarda el último intento incluso si no hay evidencia (para debug)
            retr = r
            used_q = q_try
        per_node.append({"node": node, "retrieval": retr, "used_query": used_q})

    # --- Flags + Gate ---
    flags = _flags_dispatch(_df_real, clause, jurisdiction, per_node) or []
    gate_status = "OK" if any(
        (it.get("retrieval", {}).get("status") == "OK" and it.get("retrieval", {}).get("citations"))
        for it in per_node
    ) else "NO_EVIDENCE"
    gate = {"status": gate_status}

    # No generated advice or score when retrieval found no admissible evidence.
    if gate_status == "OK":
        opinion = draft_opinion_llm(clause, jurisdiction, per_node, flags) or {}
        if "analysis_md" not in opinion and "analysis" in opinion:
            opinion["analysis_md"] = opinion.get("analysis")
        alternative = _alt_dispatch(_pa_real, clause, jurisdiction, flags) or ""
        score = _eee_dispatch(_eee_real, per_node, flags, gate)
        engine = "LLM" if os.getenv("USE_LLM", "0") == "1" else "MOCK"
    else:
        opinion, alternative, score = {}, "", None
        engine = "NOT_RUN"

    result = {
        "engine": engine,
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
