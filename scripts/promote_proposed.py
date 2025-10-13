import shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSED = ROOT / "data" / "snapshots" / "proposed"
BASELINE = ROOT / "data" / "snapshots" / "baseline"
PROPOSED.mkdir(parents=True, exist_ok=True)
BASELINE.mkdir(parents=True, exist_ok=True)

def main():
    moved = 0
    for p in PROPOSED.glob("*"):
        if p.is_file():
            target = BASELINE / p.name
            shutil.copy2(p, target)
            moved += 1
    # limpia carpeta proposed si estaba poblada
    if moved:
        for p in PROPOSED.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
    print(f"[promote] moved {moved} file(s) to baseline.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
