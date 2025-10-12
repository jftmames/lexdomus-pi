import json
from pathlib import Path
from app.pipeline import analyze_clause

CASES = Path(__file__).resolve().parent / "casos_frontera.jsonl"

def main():
    ok = 0
    total = 0
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        rec = json.loads(line)
        res = analyze_clause(rec["clause"], rec["jurisdiction"])
        expected = rec["expected_flag"]
        if expected == "OK":
            passed = (len(res["flags"]) == 0)
        else:
            passed = (expected in res["flags"])
        print(f"[{rec['id']}] expected={expected} got={res['flags']} -> {'PASS' if passed else 'FAIL'}")
        ok += int(passed)
    print(f"{ok}/{total} passed")
    if ok != total:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
