import json
from pathlib import Path
from lex_domus.flagger import detect_flags

CASES = Path(__file__).resolve().parent / "casos_frontera.jsonl"

def main():
    ok = 0
    total = 0
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        rec = json.loads(line)
        # These inherited cases assert flags only, including EU/INT cases outside
        # the ES pilot. Exercise that component without bypassing runtime policy.
        flags = detect_flags(rec["clause"], rec["jurisdiction"])
        expected = rec["expected_flag"]
        if expected == "OK":
            passed = (len(flags) == 0)
        else:
            passed = (expected in flags)
        print(f"[{rec['id']}] expected={expected} got={flags} -> {'PASS' if passed else 'FAIL'}")
        ok += int(passed)
    print(f"{ok}/{total} passed")
    if ok != total:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
