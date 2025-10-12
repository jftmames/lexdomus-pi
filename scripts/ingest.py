import os, json, re, hashlib, pathlib, textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "corpus"
CHUNKS_DIR = ROOT / "data" / "docs_chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

def detect_source_and_meta(path: pathlib.Path):
    name = path.name.lower()
    if "lpi" in name:
        return "BOE", "ES", "LPI (España)"
    if "infosoc" in name:
        return "EUR-Lex", "EU", "Directiva 2001/29/CE (InfoSoc)"
    if "berne" in name:
        return "WIPO/OMPI", "INT", "Convenio de Berna"
    if "usc_17" in name:
        return "USC (Cornell/LII)", "US", "17 U.S.C."
    return "UNKNOWN", "INT", path.stem

def chunk_text(txt: str, size=800, overlap=120):
    # Limpieza simple
    txt = re.sub(r"\s+", " ", txt).strip()
    chunks = []
    i = 0
    while i < len(txt):
        chunk = txt[i:i+size]
        chunks.append(chunk)
        i += size - overlap
    return chunks

def main():
    out_path = CHUNKS_DIR / "chunks.jsonl"
    with open(out_path, "w", encoding="utf-8") as out:
        for f in sorted(CORPUS_DIR.glob("*.txt")):
            src, juris, title = detect_source_and_meta(f)
            txt = f.read_text(encoding="utf-8")
            chunks = chunk_text(txt)
            for idx, ch in enumerate(chunks):
                doc_id = f"{f.stem}#c{idx:03d}"
                ref = ""
                # heurística de referencia (muy básica)
                if "artículo 14" in ch.lower() or "6bis" in ch.lower() or "§106" in ch:
                    ref = "pinpoint"
                rec = {
                    "doc_id": doc_id,
                    "source": src,
                    "jurisdiction": juris,
                    "title": title,
                    "ref": ref,
                    "text": ch
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Chunks escritos en {out_path}")

if __name__ == "__main__":
    main()
