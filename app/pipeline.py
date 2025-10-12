from typing import Dict, Any, List
from pathlib import Path
import json

from verdiktia.inquiry_engine import decompose_clause
from lex_domus.rag_pipeline import source_required_answer, load_policy
from lex_domus.flagger import detect_flags, propose_alternative
from metrics_eee.scorer import score_eee
from metrics_eee.logger import append_log
from app.writer import draft_opinion

LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "logs" / "ledger.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

def _read_last_hash() -> str:
    if not LOG_PATH.exists():
        return ""
    last = ""
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line).get("hash","")
    return last

def analyze_clause(clause: str, jurisdiction: str) -> Dict[str, Any]:
    policy = load_policy()

    # 1) Inquiry Graph
    nodes = decompose_clause(clause, jurisdiction)

    # 2) Recuperación por nodo
    per_node = []
    for n in nodes:
        q = f"{n['pregunta']} | Jurisdicción: {jurisdiction} | Cláusula: {clause[:400]}"
        res = source_required_answer(q, k=policy["rag"]["retrieval"]["top_k"])
        per_node.append({"node": n, "retrieval": res})

    # 3) EEE (heurístico: T = % nodos con al menos una cita pinpoint)
    propos = []
    for item in per_node:
        cit_ok = False
        retr = item["retrieval"]
        if retr["status"] == "OK":
            cit_ok = any(c.get("meta", {}).get("pinpoint") for c in retr.get("citations", []))
        propos.append({"cita_pinpoint": cit_ok})

    analysis_stub = {
        "proposiciones": propos,
        "tiene_rha": any(p["cita_pinpoint"] for p in propos),
        "alternativas": True
    }
    T, J, P, flags_in = score_eee(analysis_stub)

    # 4) Flags por contenido
    flags = sorted(set(flags_in + detect_flags(clause, jurisdiction)))

    # 5) Redactor determinista (sin LLM)
    opinion = draft_opinion(clause, jurisdiction, per_node, flags)

    # 6) Alternativa base
    alternative = propose_alternative(clause, jurisdiction)

    # 7) Ensamble y logging
    result = {
        "jurisdiction": jurisdiction,
        "inquiry_nodes": nodes,
        "per_node": per_node,
        "EEE": {"T": T, "J": J, "P": P},
        "flags": flags,
        "opinion": opinion,
        "alternative_clause": alternative,
        "policy": {
            "min_citations": policy["rag"]["thresholds"]["min_citations"],
            "require_pinpoint": policy["rag"]["thresholds"]["require_pinpoint"]
        }
    }

    prev = _read_last_hash()
    append_log(str(LOG_PATH), {
        "input": {"clause": clause, "jurisdiction": jurisdiction},
        "output": {"EEE": result["EEE"], "flags": flags},
        "nodes": nodes
    }, prev)

    return result
