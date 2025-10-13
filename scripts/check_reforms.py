import os, sys, json, hashlib, difflib, datetime, pathlib
from typing import Dict, List, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
BASELINE = ROOT / "data" / "snapshots" / "baseline"
PROPOSED = ROOT / "data" / "snapshots" / "proposed"
STATUS = ROOT / "data" / "status"
STATUS.mkdir(parents=True, exist_ok=True)
BASELINE.mkdir(parents=True, exist_ok=True)
PROPOSED.mkdir(parents=True, exist_ok=True)

# Mantén esta lista alineada con fetch_corpus.py
KNOWN_FULLS = [
    "es_lpi_full.txt",
    "eu_infosoc_full.txt",
    "berne_full.txt",
    "us_usc_17_106.txt",
    "us_usc_17_201.txt",
    "us_usc_17_302.txt",
]

URLS = {
    "es_lpi_full.txt": "https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930",
    "eu_infosoc_full.txt": "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX%3A32001L0029",
    "berne_full.txt": "https://www.wipo.int/wipolex/es/text/283698",
    "us_usc_17_106.txt": "https://www.law.cornell.edu/uscode/text/17/106",
    "us_usc_17_201.txt": "https://www.law.cornell.edu/uscode/text/17/201",
    "us_usc_17_302.txt": "https://www.law.cornell.edu/uscode/text/17/302",
}

def _sha256(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _write(p: pathlib.Path, txt: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")

def _unified_diff(a: str, b: str, fromfile: str, tofile: str) -> str:
    return "\n".join(difflib.unified_diff(
        a.splitlines(), b.splitlines(),
        fromfile=fromfile, tofile=tofile, lineterm=""
    ))

def _ratio(a: str, b: str) -> float:
    # 1.0 = idéntico; 0.0 = totalmente distinto
    return difflib.SequenceMatcher(None, a, b).ratio()

def main():
    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    report = {
        "timestamp": ts,
        "changed_count": 0,
        "docs": []
    }

    # Inicializa baseline si falta (sin marcar cambios)
    initialized = False
    for fname in KNOWN_FULLS:
        src = CORPUS / fname
        base = BASELINE / fname
        if src.exists() and not base.exists():
            _write(base, _read(src))
            initialized = True

    for fname in KNOWN_FULLS:
        src = CORPUS / fname
        base = BASELINE / fname
        if not src.exists():
            # si falta el corpus fuente, seguimos pero lo marcamos como no disponible
            report["docs"].append({
                "name": fname, "available": False, "changed": False,
                "url": URLS.get(fname, "")
            })
            continue

        cur = _read(src)
        old = _read(base)
        cur_h, old_h = _sha256(cur), _sha256(old) if old else ""
        changed = (old != "" and cur_h != old_h)

        entry = {
            "name": fname,
            "available": True,
            "url": URLS.get(fname, ""),
            "old_sha256": old_h,
            "new_sha256": cur_h,
            "changed": changed,
            "similarity": _ratio(old, cur) if old else 1.0,
            "diff_path": None,
            "proposed_path": None,
            "baseline_path": str(base.relative_to(ROOT)) if base.exists() else None,
        }

        if changed:
            report["changed_count"] += 1
            # guarda proposed para revisión
            proposed = PROPOSED / fname
            _write(proposed, cur)
            entry["proposed_path"] = str(proposed.relative_to(ROOT))

            # genera diff unificado
            diff = _unified_diff(old, cur, fromfile=f"baseline/{fname}", tofile=f"proposed/{fname}")
            diff_path = STATUS / f"diff_{fname.replace('.txt','')}.patch"
            _write(diff_path, diff)
            entry["diff_path"] = str(diff_path.relative_to(ROOT))

        report["docs"].append(entry)

    # escribe reporte
    _write(STATUS / "reforms_report.json", json.dumps(report, ensure_ascii=False, indent=2))

    # resumen para GitHub
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as s:
            s.write("## Watcher de reformas — estado\n")
            s.write(f"- Fecha (UTC): **{ts}**\n")
            s.write(f"- Documentos con cambios: **{report['changed_count']}**\n")
            for d in report["docs"]:
                if d["changed"]:
                    s.write(f"  - {d['name']}: similarity {d['similarity']:.3f} → diff: `{d['diff_path']}`\n")
            if initialized:
                s.write("\n_Nota:_ baseline inicializada con el corpus actual (no se marcan cambios en esta ejecución).\n")

    print(f"[watch] changed_count={report['changed_count']}")
    # salidas para el workflow
    print(f"::set-output name=changed_count::{report['changed_count']}")

if __name__ == "__main__":
    main()
