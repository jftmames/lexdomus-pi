import re, sys, requests
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corpus"
OUT.mkdir(parents=True, exist_ok=True)

def fetch_text(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent":"lexdomus-pi/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # texto bruto; evitamos navegación específica (cada portal es distinto)
    text = soup.get_text("\n")
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def slice_between_markers(txt: str, pattern_start: str, pattern_end: str | None) -> str:
    start = re.search(pattern_start, txt, flags=re.IGNORECASE)
    if not start:
        return txt
    s = start.start()
    if pattern_end:
        end = re.search(pattern_end, txt, flags=re.IGNORECASE)
        e = end.start() if end else len(txt)
    else:
        e = len(txt)
    return txt[s:e].strip()

def write_file(name: str, txt: str):
    path = OUT / name
    path.write_text(txt, encoding="utf-8")
    print(f"[fetch] Escrito {path}")

def main():
    # 1) LPI ES (BOE)
    try:
        lpi = fetch_text("https://www.boe.es/buscar/act.php?id=BOE-A-1996-8932")
        # recorta a arts. 14–23 y 43–47 si se detectan
        lpi_sel_a = slice_between_markers(lpi, r"Artículo\s+14", r"Artículo\s+24")
        lpi_sel_b = slice_between_markers(lpi, r"Artículo\s+43", r"Artículo\s+48")
        lpi_final = (lpi_sel_a + "\n\n" + lpi_sel_b).strip()
        write_file("es_lpi.txt", lpi_final if len(lpi_final) > 500 else lpi)
    except Exception as e:
        print("[warn] LPI: fallo al descargar, usa corpus manual.", e)

    # 2) InfoSoc UE (EUR-Lex)
    try:
        infosoc = fetch_text("https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32001L0029")
        write_file("eu_infosoc.txt", infosoc)
    except Exception as e:
        print("[warn] InfoSoc: fallo al descargar, usa corpus manual.", e)

    # 3) Berna (OMPI) — si falla, escribe 6bis mínimo
    try:
        berna = fetch_text("https://www.wipo.int/wipolex/es/text/283693")
        # recorta a 6bis si se detecta
        berna_6bis = slice_between_markers(berna, r"Artículo\s+6bis", r"Artículo\s+7")
        if len(berna_6bis) < 120:
            berna_6bis = "Artículo 6bis — Derechos morales. Independientemente de los derechos patrimoniales, el autor conservará el derecho de reivindicar la paternidad de la obra y de oponerse a toda deformación que perjudique su honor o reputación."
        write_file("berne.txt", berna_6bis)
    except Exception as e:
        print("[warn] Berna: fallo al descargar; escribo 6bis mínimo.", e)
        write_file("berne.txt", "Artículo 6bis — Derechos morales. Independientemente de los derechos patrimoniales, el autor conserva el derecho de paternidad e integridad.")

    # 4) 17 U.S.C. — Cornell LII (106, 201, 302)
    try:
        us_106 = fetch_text("https://www.law.cornell.edu/uscode/text/17/106")
        us_201 = fetch_text("https://www.law.cornell.edu/uscode/text/17/201")
        us_302 = fetch_text("https://www.law.cornell.edu/uscode/text/17/302")
        write_file("us_usc_17.txt", f"§106\n{us_106}\n\n§201\n{us_201}\n\n§302\n{us_302}")
    except Exception as e:
        print("[warn] USC: fallo al descargar, usa corpus manual.", e)

if __name__ == "__main__":
    main()
