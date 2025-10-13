import os, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.pipeline import analyze_clause
except ModuleNotFoundError as e:
    # Diagnóstico útil en el runner
    print("[DEBUG] sys.path:", sys.path)
    print("[DEBUG] ROOT exists:", ROOT.exists())
    print("[DEBUG] app package path:", ROOT / "app")
    raise

def main():
    clause = os.getenv("CLAUSE", "").strip()
    juris = os.getenv("JURISDICTION", "ES").strip()
    if not clause:
        raise SystemExit("CLAUSE vacío. Proporciona un texto al lanzar el workflow.")
    os.environ["USE_LLM"] = "1"  # fuerza LLM en este script

    res = analyze_clause(clause, juris)
    out_path = "llm_preview_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res.get("EEE"), ensure_ascii=False))
    print(f"Escrito: {out_path}")

if __name__ == "__main__":
    main()
