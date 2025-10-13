import os, sys, json, csv, statistics
from pathlib import Path
from typing import Dict, Any, List

# Asegura import del repo
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline import analyze_clause

def count_citations(res: Dict[str, Any]) -> int:
    total = 0
    for item in res.get("per_node", []):
        retr = item.get("retrieval", {})
        if retr.get("status") == "OK":
            total += len(retr.get("citations", []))
    return total

def main():
    cases_path = Path(os.getenv("CASES_PATH", "tests/casos_frontera.jsonl"))
    strict = os.getenv("STRICT", "0").strip() == "1"
    min_pass_rate = float(os.getenv("MIN_PASS_RATE", "0.60"))
    # Fuerza uso LLM
    os.environ["USE_LLM"] = "1"

    lines = [l for l in cases_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows: List[Dict[str, Any]] = []
    passed_flags = 0
    passed_gates = 0
    Ts, Js, Ps = [], [], []

    details = {}
    for line in lines:
        rec = json.loads(line)
        rid = rec["id"]
        clause = rec["clause"]
        juris = rec["jurisdiction"]
        exp_flag = rec.get("expected_flag")

        res = analyze_clause(clause, juris)
        flags = res.get("flags", [])
        gate = res.get("gate", {"status": "UNKNOWN"})
        eee = res.get("EEE", {"T": 0, "J": 0, "P": 0})
        cits = count_citations(res)

        flag_pass = (exp_flag == "OK" and len(flags) == 0) or (exp_flag != "OK" and exp_flag in flags)
        gate_pass = (gate.get("status") == "OK")

        if flag_pass: passed_flags += 1
        if gate_pass: passed_gates += 1
        Ts.append(eee.get("T", 0)); Js.append(eee.get("J", 0)); Ps.append(eee.get("P", 0))

        rows.append({
            "id": rid,
            "jurisdiction": juris,
            "expected_flag": exp_flag,
            "flags_found": "|".join(flags) if flags else "",
            "gate_status": gate.get("status"),
            "EEE_T": f"{eee.get('T',0):.2f}",
            "EEE_J": f"{eee.get('J',0):.2f}",
            "EEE_P": f"{eee.get('P',0):.2f}",
            "citations_total": cits,
            "engine": res.get("engine", "MOCK")
        })
        # guarda detalle completo por si hace falta inspección
        details[rid] = res

    total = len(rows)
    pass_rate_flags = passed_flags / total if total else 0
    pass_rate_gate  = passed_gates / total if total else 0
    mean_T = statistics.mean(Ts) if Ts else 0
    mean_J = statistics.mean(Js) if Js else 0
    mean_P = statistics.mean(Ps) if Ps else 0

    # CSV
    csv_path = Path("llm_eval_results.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # JSON de detalle
    json_path = Path("llm_eval_details.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "cases": total,
                "pass_rate_flags": pass_rate_flags,
                "pass_rate_gate": pass_rate_gate,
                "EEE_mean": {"T": mean_T, "J": mean_J, "P": mean_P}
            },
            "rows": rows
        }, f, ensure_ascii=False, indent=2)

    # Resumen para GitHub (si existe env)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write("## LLM Eval — resumen\n")
            s.write(f"- Casos: **{total}**\n")
            s.write(f"- Pass rate (flags esperados): **{pass_rate_flags:.0%}**\n")
            s.write(f"- Pass rate (gate OK): **{pass_rate_gate:.0%}**\n")
            s.write(f"- EEE medias: T {mean_T:.2f} · J {mean_J:.2f} · P {mean_P:.2f}\n")
            s.write(f"- Artefactos: `llm_eval_results.csv`, `llm_eval_details.json`\n")

    # Si strict, haz fallar por debajo de umbral
    if strict and pass_rate_flags < min_pass_rate:
        raise SystemExit(f"Fail (strict): pass_rate_flags={pass_rate_flags:.2%} < {min_pass_rate:.2%}")

    print(f"OK · resultados en {csv_path} y {json_path}")

if __name__ == "__main__":
    main()
