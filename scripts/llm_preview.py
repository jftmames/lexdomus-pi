import os, json, sys
from pathlib import Path

# --- Garantiza que el repo raíz esté en sys.path (import app.*) ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline import analyze_clause

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
