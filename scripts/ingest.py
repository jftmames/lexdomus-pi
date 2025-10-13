import os, json, re, pathlib
from typing import List, Dict

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "corpus"
CHUNKS_DIR = ROOT / "data" / "docs_chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# --------- Helpers de metadatos ---------

def detect_meta(path: pathlib.Path) -> Dict[str, str]:
    name = path.name.lower()
    if "lpi" in name:
        return {"source": "BOE", "jurisdiction": "ES", "title": "Ley de Propiedad Intelectual (España)", "family": "LPI"}
    if "infosoc" in name or "2001_29" in name:
        return {"source": "EUR-Lex", "jurisdiction": "EU", "title": "Directiva 2001/29/CE (InfoSoc)", "family": "INFOSOC"}
    if "berne" in name or "berna" in name:
        return {"source": "WIPO/OMPI", "jurisdiction": "INT", "title": "Convenio de Berna", "family": "BERNE"}
    if "usc_17" in name or "us_usc_17" in name:
        return {"source": "USC (Cornell/LII)", "jurisdiction": "US", "title": "17 U.S.C.", "family": "USC17"}
    return {"source": "UNKNOWN", "jurisdiction": "INT", "title": path.stem, "family": "GEN"}

def build_ref(chunk_text: str, family: str) -> Dict[str, str]:
    t = chunk_text
    # LPI: Artículo N
    if family == "LPI":
        m = re.search(r"(Artículo|Art\.)\s+(\d+)\b", t, re.IGNORECASE)
        if m:
            art = m.group(2)
            return {
                "ref_label": f"LPI art. {art}",
                "ref_url": "https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930",  # enlace general consolidado
            }
    # InfoSoc (no tiene art. tipo LPI en tu extracto mínimo)
    if family == "INFOSOC":
        m = re.search(r"(Art(í|i)culo|Article)\s+(\d+)", t, re.IGNORECASE)
        label = f"InfoSoc art. {m.group(3)}" if m else "InfoSoc (considerandos/art.)"
        return {
            "ref_label": label,
            "ref_url": "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX%3A32001L0029",
        }
    # Berna: 6bis
    if family == "BERNE":
        if re.search(r"\b6bis\b", t, re.IGNORECASE):
            return {
                "ref_label": "Berna art. 6bis",
                "ref_url": "https://www.wipo.int/wipolex/es/text/283698",
            }
        m = re.search(r"(Art(í|i)culo|Article)\s+(\d+)\b", t, re.IGNORECASE)
        if m:
            return {
                "ref_label": f"Berna art. {m.group(3)}",
                "ref_url": "https://www.wipo.int/wipolex/es/text/283698",
            }
        return {"ref_label": "Berna (general)", "ref_url": "https://www.wipo.int/wipolex/es/text/283698"}
    # 17 USC: §106 / §201 / §302
    if family == "USC17":
        for sec in ("106", "201", "302"):
            if re.search(rf"(\b§\s*{sec}\b|\b{sec}\b)", t):
                return {
                    "ref_label": f"17 USC §{sec}",
                    "ref_url": f"https://www.law.cornell.edu/uscode/text/17/{sec}",
                }
        return {"ref_label": "17 USC (general)", "ref_url": "https://www.law.cornell.edu/uscode/text/17"}
    return {"ref_label": "", "ref_url": ""}

def group_lines(lines: List[str], max_chars=900, overlap_lines=2):
    """Agrupa líneas en bloques ~max_chars controlando un solape pequeño (por líneas)."""
    chunks = []
    start = 0
    while start < len(lines):
        size = 0
        end = start
        while end < len(lines) and size + len(lines[end]) + 1 <= max_chars:
            size += len(lines[end]) + 1
            end += 1
        # bloque
        text = "\n".join(lines[start:end]).strip()
        if text:
            chunks.append((start+1, end, text))  # líneas 1-indexed
        # avanza con solape
        start = max(end - overlap_lines, end) if end > start else end + 1
    return chunks

# --------- Main ---------

def main():
    out_path = CHUNKS_DIR / "chunks.jsonl"
    with open(out_path, "w", encoding="utf-8") as out:
        for f in sorted(CORPUS_DIR.glob("*.txt")):
            meta_base = detect_meta(f)
            raw = f.read_text(encoding="utf-8")
            # normaliza saltos de línea (mejor para anchors de línea)
            raw = re.sub(r"\r\n?", "\n", raw).strip()
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
            for idx, (l0, l1, text) in enumerate(group_lines(lines, max_chars=1000, overlap_lines=2)):
                doc_id = f"{f.stem}#c{idx:03d}"
                ref = build_ref(text, meta_base["family"])
                record = {
                    "doc_id": doc_id,
                    "source": meta_base["source"],
                    "jurisdiction": meta_base["jurisdiction"],
                    "title": meta_base["title"],
                    "family": meta_base["family"],
                    "ref_label": ref["ref_label"],
                    "ref_url": ref["ref_url"],
                    "pinpoint": bool(ref["ref_label"]),   # True si detectamos referencia
                    "line_start": l0,
                    "line_end": l1,
                    "text": text
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[ingest] Chunks -> {out_path}")

if __name__ == "__main__":
    main()

