import os, sys, json, datetime
from pathlib import Path
from typing import Dict, Any, List

# Asegura import del repo
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATUS_DIR = ROOT / "data" / "status"
STATUS_DIR.mkdir(parents=True, exist_ok=True)

def read_jsonl_count(path: Path) -> int:
    if not path.exists(): return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f if _.strip())

def read_chunks_families(path: Path) -> Dict[str, int]:
    fam: Dict[str,int] = {}
    if not path.exists(): return fam
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            family = rec.get("family", "GEN")
            fam[family] = fam.get(family, 0) + 1
    return dict(sorted(fam.items(), key=lambda kv: kv[0]))

def load_last_families() -> Dict[str,int]:
    p = STATUS_DIR / "last_families.json"
    if not p.exists(): return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_last_families(fam: Dict[str,int]) -> None:
    (STATUS_DIR / "last_families.json").write_text(json.dumps(fam, ensure_ascii=False, indent=2), encoding="utf-8")

def eval_cases(cases_path: Path, use_llm: bool) -> Dict[str, Any]:
    from app.pipeline import analyze_clause
    if not cases_path.exists():
        return {"cases": 0, "pass_rate_flags": None, "pass_rate_gate": None, "EEE_mean": None, "engine": None}
    # Fuerza motor
    os.environ["USE_LLM"] = "1" if use_llm else "0"

    lines = [l for l in cases_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    passed_flags = passed_gates = total = 0
    Ts: List[float] = []; Js: List[float] = []; Ps: List[float] = []
    engine_seen = None
    for line in lines:
        rec = json.loads(line)
        res = analyze_clause(rec["clause"], rec["jurisdiction"])
        engine_seen = engine_seen or res.get("engine")
        flags = res.get("flags", [])
        gate = res.get("gate", {"status": "UNKNOWN"})
        eee = res.get("EEE", {"T": 0, "J": 0, "P": 0})

        expected = rec.get("expected_flag")
        flag_pass = (expected == "OK" and len(flags) == 0) or (expected != "OK" and expected in flags)
        gate_pass = (gate.get("status") == "OK")

        passed_flags += int(flag_pass)
        passed_gates += int(gate_pass)
        Ts.append(eee.get("T", 0)); Js.append(eee.get("J", 0)); Ps.append(eee.get("P", 0))
        total += 1

    def mean(xs: List[float]) -> float:
        return round(sum(xs)/len(xs), 2) if xs else 0.0

    return {
        "cases": total,
        "pass_rate_flags": round(passed_flags/total, 2) if total else None,
        "pass_rate_gate": round(passed_gates/total, 2) if total else None,
        "EEE_mean": {"T": mean(Ts), "J": mean(Js), "P": mean(Ps)},
        "engine": engine_seen
    }

def main():
    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    chunks = ROOT / "data" / "docs_chunks" / "chunks.jsonl"
    indices = ROOT / "indices"
    bm25_ok = (indices / "bm25.pkl").exists()
    faiss_ok = (indices / "faiss.index").exists()
    emb_ok = (indices / "embeddings.npy").exists()

    n_chunks = read_jsonl_count(chunks)
    fam_now = read_chunks_families(chunks)
    fam_prev = load_last_families()
    save_last_families(fam_now)  # deja snapshot para el próximo diff

    # Diff de familias (curr - prev)
    fam_diff_lines: List[str] = []
    if fam_prev:
        keys = sorted(set(fam_now) | set(fam_prev))
        for k in keys:
            prev = fam_prev.get(k, 0)
            cur  = fam_now.get(k, 0)
            delta = cur - prev
            sign = "±0"
            if delta > 0: sign = f"+{delta}"
            elif delta < 0: sign = f"{delta}"
            fam_diff_lines.append(f"- {k}: {prev} → {cur} (**{sign}**)")
    else:
        fam_diff_lines.append("_Primera ejecución: no hay baseline previo de familias._")

    # Watcher report
    reforms_report = ROOT / "data" / "status" / "reforms_report.json"
    changed = 0
    if reforms_report.exists():
        try:
            changed = json.loads(reforms_report.read_text(encoding="utf-8")).get("changed_count", 0)
        except Exception:
            changed = -1

    # Eval rápida (por defecto MOCK). Actívala con ENABLE_LLM_EVAL=1 + OPENAI_API_KEY en el workflow.
    use_llm = os.getenv("ENABLE_LLM_EVAL", "0").strip() == "1" and os.getenv("OPENAI_API_KEY", "")
    eval_res = eval_cases(ROOT / "tests" / "casos_frontera.jsonl", bool(use_llm))

    # App URL (si está desplegada y configurada)
    app_url = os.getenv("APP_URL", "").strip()

    # Render comentario
    lines: List[str] = []
    lines.append(f"## Rebuild completado — {ts}\n")
    lines.append("### Corpus & índices")
    lines.append(f"- Chunks: **{n_chunks}**")
    if fam_now:
        fam_txt = ", ".join([f"{k}: {v}" for k,v in fam_now.items()])
        lines.append(f"- Familias actuales: {fam_txt}")
    lines.append(f"- Índices: BM25={'✅' if bm25_ok else '❌'} · FAISS={'✅' if faiss_ok else '❌'} · Embeddings={'✅' if emb_ok else '❌'}\n")

    lines.append("### Cambios por familia (respecto al rebuild anterior)")
    lines.extend(fam_diff_lines)
    lines.append("")

    lines.append("### Watcher")
    if changed == 0:
        lines.append("- Cambios pendientes: **0** (baseline al día)")
    elif changed > 0:
        lines.append(f"- Cambios pendientes: **{changed}** (revisa `data/status/reforms_report.json`)")
    else:
        lines.append("- Cambios pendientes: **N/D** (no se pudo leer el reporte)")
    lines.append("")

    lines.append("### Evaluación rápida (casos frontera)")
    if eval_res["cases"]:
        prf = f"{int(eval_res['pass_rate_flags']*100)}%" if eval_res["pass_rate_flags"] is not None else "N/D"
        prg = f"{int(eval_res['pass_rate_gate']*100)}%" if eval_res["pass_rate_gate"] is not None else "N/D"
        eee = eval_res["EEE_mean"] or {"T":0,"J":0,"P":0}
        engine = eval_res["engine"] or ("LLM" if use_llm else "MOCK")
        lines.append(f"- Casos: **{eval_res['cases']}** · Motor: **{engine}**")
        lines.append(f"- Pass-rate (flags esperados): **{prf}** · Gate OK: **{prg}**")
        lines.append(f"- EEE medio: **T {eee['T']} · J {eee['J']} · P {eee['P']}**")
    else:
        lines.append("- Sin `tests/casos_frontera.jsonl`; no se ejecutó evaluación.")
    lines.append("")

    if app_url:
        lines.append("### App")
        lines.append(f"- Acceso directo: **{app_url}**\n")

    lines.append("_Este comentario fue generado automáticamente tras el merge del PR del watcher._")

    out = ROOT / "rebuild_comment.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summary] escrito {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
