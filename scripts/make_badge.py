import os, sys, json
from pathlib import Path
from typing import Any, Dict, List

# Asegura imports del repo
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_JSON = ROOT / "data" / "status" / "eee_shield.json"
CASES = ROOT / "tests" / "casos_frontera.jsonl"

def _eval_cases(use_llm: bool) -> Dict[str, Any]:
    from app.pipeline import analyze_clause
    if not CASES.exists():
        return {"cases": 0, "pass_rate_flags": None, "pass_rate_gate": None, "engine": None}

    os.environ["USE_LLM"] = "1" if use_llm else "0"

    lines = [l for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = len(lines)
    passed_flags = 0
    passed_gate  = 0
    engine = None
    for line in lines:
        rec = json.loads(line)
        res = analyze_clause(rec["clause"], rec["jurisdiction"])
        engine = engine or res.get("engine")
        flags = res.get("flags", [])
        gate  = res.get("gate", {"status": "UNKNOWN"})

        exp = rec.get("expected_flag")
        ok_flag = (exp == "OK" and len(flags) == 0) or (exp != "OK" and exp in flags)
        ok_gate = (gate.get("status") == "OK")

        passed_flags += int(ok_flag)
        passed_gate  += int(ok_gate)

    pr_flags = passed_flags/total if total else 0.0
    pr_gate  = passed_gate/total if total else 0.0
    return {"cases": total, "pass_rate_flags": pr_flags, "pass_rate_gate": pr_gate, "engine": engine or ("LLM" if use_llm else "MOCK")}

def _color(p: float) -> str:
    # Verde >=80%, Ámbar 60–79%, Rojo <60%
    if p >= 0.80: return "green"
    if p >= 0.60: return "yellow"
    return "red"

def main():
    use_llm = os.getenv("ENABLE_LLM_EVAL", "0").strip() == "1" and os.getenv("OPENAI_API_KEY", "")
    res = _eval_cases(bool(use_llm))

    # Score conservador: el mínimo entre pass-rate de flags y gate
    if res["cases"] == 0:
        score = 0.0
        label = "EEE"
        message = "sin casos"
        color = "lightgrey"
    else:
        pr_flags = res["pass_rate_flags"]
        pr_gate  = res["pass_rate_gate"]
        score = min(pr_flags, pr_gate)
        label = "EEE salud"
        message = f"{round(score*100):d}%"
        color = _color(score)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color
    }, ensure_ascii=False), encoding="utf-8")

    print(f"[badge] escrito {OUT_JSON} -> {label}: {message} ({color})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
