import csv, json, sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "docs_chunks" / "chunks.jsonl"
STATUS = ROOT / "data" / "status"
STATUS.mkdir(parents=True, exist_ok=True)

HIST = STATUS / "families_history.csv"
DELT = STATUS / "families_deltas.csv"

def now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def count_families() -> Dict[str,int]:
    counts: Dict[str,int] = {}
    if not CHUNKS.exists():
        return counts
    with CHUNKS.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): 
                continue
            rec = json.loads(line)
            fam = rec.get("family", "GEN")
            counts[fam] = counts.get(fam, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))

def read_csv(path: Path) -> List[Dict[str,str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: List[Dict[str,str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    snap = count_families()
    ts = now_utc_iso()

    # --- Actualiza families_history.csv ---
    hist_rows = read_csv(HIST)
    # Detecta familias históricas
    fams_hist = set()
    for r in hist_rows:
        fams_hist |= {k for k in r.keys() if k not in ("timestamp","total")}
    fams_now = set(snap.keys())
    fams_all = sorted(fams_hist | fams_now)

    # Reescribe historial con todas las columnas (rellena 0 donde falte)
    new_rows: List[Dict[str,str]] = []
    for r in hist_rows:
        nr = {"timestamp": r.get("timestamp",""), "total": r.get("total","0")}
        for fam in fams_all:
            nr[fam] = r.get(fam, "0")
        new_rows.append(nr)

    # Añade la fila actual
    total_now = sum(snap.values())
    row_now = {"timestamp": ts, "total": str(total_now)}
    for fam in fams_all:
        row_now[fam] = str(snap.get(fam, 0))
    new_rows.append(row_now)

    write_csv(HIST, new_rows, ["timestamp","total"] + fams_all)

    # --- Actualiza families_deltas.csv (delta contra última fila previa) ---
    prev = hist_rows[-1] if hist_rows else None
    delta_row = {"timestamp": ts, "total": "0"}
    if prev:
        prev_total = int(prev.get("total","0") or 0)
        delta_row["total"] = str(total_now - prev_total)
        for fam in fams_all:
            prev_v = int(prev.get(fam, "0") or 0)
            delta_row[fam] = str(snap.get(fam, 0) - prev_v)
    else:
        delta_row["total"] = str(total_now)
        for fam in fams_all:
            delta_row[fam] = str(snap.get(fam, 0))

    # Si ya hay deltas antiguos, normaliza columnas
    delt_rows = read_csv(DELT)
    for r in delt_rows:
        for fam in fams_all:
            r.setdefault(fam, "0")

    delt_rows.append(delta_row)
    write_csv(DELT, delt_rows, ["timestamp","total"] + fams_all)

    print(f"[trends] history -> {HIST}")
    print(f"[trends] deltas  -> {DELT}")

if __name__ == "__main__":
    sys.exit(main())
