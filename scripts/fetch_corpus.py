import re, requests, pathlib
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corpus"
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = [
    # LPI (BOE consolidado)
    ("es_lpi_full.txt", "https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930"),
    # InfoSoc
    ("eu_infosoc_full.txt", "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX%3A32001L0029"),
    # Berna (WIPO - texto consolidado)
    ("berne_full.txt", "https://www.wipo.int/wipolex/es/text/283698"),
    # 17 USC sections (Cornell LII)
    ("us_usc_17_106.txt", "https://www.law.cornell.edu/uscode/text/17/106"),
    ("us_usc_17_201.txt", "https://www.law.cornell.edu/uscode/text/17/201"),
    ("us_usc_17_302.txt", "https://www.law.cornell.edu/uscode/text/17/302"),
]

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # elimina scripts/estilos
    for bad in soup(["script","style","nav","header","footer"]):
        bad.decompose()
    text = soup.get_text("\n", strip=True)
    # normaliza espacios y saltos
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def fetch_one(name: str, url: str):
    print(f"[fetch] {name} <- {url}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        txt = clean_text(r.text)
        # guarda
        (OUT / name).write_text(txt, encoding="utf-8")
        print(f"[fetch] OK -> {OUT/name}")
    except Exception as e:
        print(f"[fetch] WARN: no se pudo descargar {url} ({type(e).__name__})")

def main():
    for name, url in SOURCES:
        fetch_one(name, url)
    # crea extractos mínimos compatibles con tu pipeline actual (si no existen)
    def ensure_excerpt(src, dst, patterns):
        dstp = OUT / dst
        if dstp.exists():
            return
        srcp = OUT / src
        if not srcp.exists():
            return
        txt = srcp.read_text(encoding="utf-8")
        keep = []
        for pat in patterns:
            m = re.search(pat, txt, flags=re.IGNORECASE|re.DOTALL)
            if m:
                keep.append(m.group(0))
        if keep:
            dstp.write_text("\n\n".join(keep), encoding="utf-8")
            print(f"[excerpt] {dst} creado desde {src}")
    # Ensures de compatibilidad:
    ensure_excerpt("es_lpi_full.txt", "es_lpi_excerpt.txt", [r"Artículo\s+14.*?(?=Artículo\s+\d+)", r"Artículo\s+17.*?(?=Artículo\s+\d+)"])
    ensure_excerpt("eu_infosoc_full.txt", "eu_infosoc_excerpt.txt", [r"Art(í|i)culo\s+2.*?(?=Art(í|i)culo\s+\d+)", r"Art(í|i)culo\s+3.*?(?=Art(í|i)culo\s+\d+)"])
    ensure_excerpt("berne_full.txt", "berne_excerpt.txt", [r"6bis.*?(?=\n\n|\r\r|Artículo|\Z)"])
    ensure_excerpt("us_usc_17_106.txt", "us_usc_17_excerpt.txt", [r"§\s*106.*"])
    print("[fetch] done")

if __name__ == "__main__":
    main()
