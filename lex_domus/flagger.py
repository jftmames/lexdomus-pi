import re
from typing import List, Dict

PATTERNS = {
    "renuncia moral general": [
        r"renunci[ae]\s+a\s+todos?\s+sus\s+derechos\s+morales",
        r"waiv(e|er).*(moral rights)"
    ],
    "territorialidad ambigua": [
        r"\bworldwide\b",
        r"duración máxima permitida en cualquier país",
        r"en\s+cualquier\s+país"
    ],
    "modalidades genéricas": [
        r"cualquier\s+soporte\s+conocido\s+o\s+por\s+conocerse",
        r"any\s+media\s+now\s+known\s+or\s+hereafter\s+devised"
    ],
    "cesión futura genérica": [
        r"obras?\s+futuras?\s+del\s+autor",
        r"future\s+works"
    ]
}

def detect_flags(clause: str, jurisdiction: str) -> List[str]:
    txt = clause.lower()
    found = []
    for flag, regexes in PATTERNS.items():
        for rx in regexes:
            if re.search(rx, txt, re.IGNORECASE):
                found.append(flag)
                break
    # Reglas simples por jurisdicción (ejemplo)
    if jurisdiction == "ES" and "renuncia" in txt and "morales" in txt:
        if "parcial" not in txt and "limitada" not in txt:
            if "renuncia moral general" not in found:
                found.append("renuncia moral general")
    return sorted(set(found))

def propose_alternative(clause: str, jurisdiction: str) -> str:
    # Alternativa mínima parametrizada (sin LLM)
    territorio = {"ES":"España","EU":"UE","US":"Estados Unidos","INT":"mundial"}.get(jurisdiction,"España")
    return (
        "El Titular cede a la Entidad, con carácter no exclusivo, los derechos de "
        "reproducción y distribución sobre la Obra identificada, para el territorio "
        f"{territorio}, por un plazo de 3 años, y para las modalidades de explotación "
        "descritas en Anexo I. Se respetarán los derechos morales (LPI art. 14; Berna art. 6bis)."
    )
