import os, json, re, hashlib, pathlib
from typing import Dict, List, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "corpus"
CHUNKS_DIR = ROOT / "data" / "docs_chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ---- Mapeo por archivo -> metadatos de fuente oficial ----
DOC_META = {
    # España — LPI
    "es_lpi":  {"source": "BOE",      "jurisdiction": "ES",  "title": "LPI (España)", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-1996-8932"},
    # UE — InfoSoc
    "eu_infosoc": {"source": "EUR-Lex","jurisdiction": "EU",  "title": "Directiva 2001/29/CE (InfoSoc)", "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32001L0029"},
    # OMPI — Berna
    "berne":   {"source": "WIPO/OMPI","jurisdiction": "INT", "title": "Convenio de Berna", "url": "https://www.wipo.int/wipolex/es/"},
    # EEUU — 17 U.S.C.
    "us_usc_17": {"source": "USC (Cornell/LII)","jurisdiction": "US","title": "17 U.S.C.","url": "https://www.law.cornell.edu/uscode/text/17"}
}

# ---- Detectores de artículo/§/apartado por corpus ----
RE_ART_ES = re.compile(r"(Artículo\s+(\d{1,3})(?:\s*[\.\-]|\s))", re.IGNORECASE)
RE_ART_BERNA = re.compile(r"(Artículo\s+(\d{1,3})(bis)?)", re.IGNORECASE)
RE_SEC_US = re.compile(r"(§\s*(\d{2,3})([a-z]*)\b)", re.IGNORECASE)

def chunk_text(txt: str, size=1000, overlap=150) -> List[Tuple[int, int, str]]:
    """Devuelve lista de (start, end, chunk_text) con solape."""
    chunks = []
    i = 0
    n = len(txt)
    while i < n:
        end = min(i + size, n)
        chunks.append((i, end, txt[i:end]))
        if end == n: break
        i = end - overlap
    return chunks

def detect_doc_key(path: pathlib.Path) -> str:
    name = path.stem.lower()
    for key in DOC_META:
        if key in name:
            return key
    # fallback por nombre
    if "lpi" in name: return "es_lpi"
    if "infosoc" in name: return "eu_infosoc"
    if "berne" in name or "berna" in name: return "berne"
    if "usc" in name or "us_17" in name: return "us_usc_17"
    return "unknown"

def sectionize(txt: str, key: str) -> List[Dict]:
    """
    Divide el texto en secciones por artículo/§ y devuelve lista con:
    {'ref_str': 'LPI art. 14', 'start': i, 'end': j, 'text': ...}
    """
    spans = []
    if key == "es_lpi":
        it = list(RE_ART_ES.finditer(txt))
        for i, m in enumerate(it):
            start = m.start()
            end = it[i+1].start() if i+1 < len(it) else len(txt)
            num = m.group(2)
            spans.append({"ref_str": f"LPI art. {num}", "start": start, "end": end, "text": txt[start:end]})
    elif key == "berne":
        it = list(RE_ART_BERNA.finditer(txt))
        for i, m in enumerate(it):
            start = m.start()
            end = it[i+1].start() if i+1 < len(it) else len(txt)
            num = m.group(2) + (m.group(3) or "")
            spans.append({"ref_str": f"Berna art. {num}", "start": start, "end": end, "text": txt[start:end]})
    elif key == "us_usc_17":
        it = list(RE_SEC_US.finditer(txt))
        for i, m in enumerate(it):
            start = m.start()
            end = it[i+1].start() if i+1 < len(it) else len(txt)
            num = m.group(2) + (m.group(3) or "")
            spans.append({"ref_str": f"17 U.S.C. §{num}", "start": start, "end": end, "text": txt[start:end]})
    else:
        # InfoSoc u otros: sin marcadores finos; lo dejamos entero
        spans.append({"ref_str": "", "start": 0, "end": len(txt), "text": txt})
    return spans

def main():
    out_path = CHUNKS_DIR / "chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as out:
        for f in sorted(CORPUS_DIR.glob("*.txt")):
            raw = f.read_text(encoding="utf-8")
            # Normaliza espacios
            txt = re.sub(r"\s+", " ", raw).strip()

            key = detect_doc_key(f)
            meta_base = DOC_META.get(key, {"source":"UNKNOWN","jurisdiction":"INT","title":f.stem,"url":""})

            # Secciones por artículo/§, luego chunk dentro
            sections = sectionize(txt, key)

            for s_idx, sec in enumerate(sections):
                sec_text = sec["text"]
                sec_start = sec["start"]
                chunks = chunk_text(sec_text, size=1100, overlap=180)
                for c_idx, (c_start, c_end, ch) in enumerate(chunks):
                    # Rango absoluto respecto del documento
                    abs_start = sec_start + c_start
                    abs_end = sec_start + c_end
                    rec = {
                        "doc_id": f"{f.stem}#s{s_idx:03d}c{c_idx:03d}",
                        "source": meta_base["source"],
                        "jurisdiction": meta_base["jurisdiction"],
                        "title": meta_base["title"],
                        "url": meta_base["url"],
                        "ref": sec["ref_str"],            # ej: "LPI art. 14"
                        "pinpoint": bool(sec["ref_str"]), # true si hay artículo/§ detectado
                        "line_start": abs_start,
                        "line_end": abs_end,
                        "text": ch
                    }
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[ingest] Chunks escritos en {out_path}")

if __name__ == "__main__":
    main()

