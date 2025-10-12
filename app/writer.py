from typing import Dict, Any, List
from textwrap import shorten

def _slice(txt: str, n: int = 420) -> str:
    return shorten(txt.replace("\n", " "), width=n, placeholder="…")

def _mk_cite(meta: Dict[str, Any]) -> str:
    src = meta.get("source","?")
    jur = meta.get("jurisdiction","?")
    title = meta.get("title","?")
    pin = " (pinpoint)" if meta.get("pinpoint") else ""
    return f"{title} · {src}/{jur}{pin}"

def _pros_cons_from_clause(clause: str, jurisdiction: str) -> Dict[str, List[str]]:
    clause_low = clause.lower()
    pros, cons = [], []

    # Pros básicos
    if "no exclusiva" in clause_low or "no-exclusiva" in clause_low:
        pros.append("Licencia no exclusiva: reduce riesgo de desequilibrio.")
    if "3 años" in clause_low or "tres años" in clause_low or "plazo de" in clause_low:
        pros.append("Plazo acotado: favorece proporcionalidad temporal.")
    if "anexo" in clause_low or "modalidades" in clause_low:
        pros.append("Modalidades/soportes enumerados: mayor seguridad jurídica.")

    # Cons básicos
    if "worldwide" in clause_low or "cualquier país" in clause_low:
        cons.append("Territorialidad amplia o ambigua (worldwide) sin precisión adicional.")
    if "cualquier soporte conocido o por conocerse" in clause_low:
        cons.append("Cláusula de modalidades genéricas (riesgo de nulidad/abusividad).")
    if "renuncia" in clause_low and "morales" in clause_low and jurisdiction == "ES":
        cons.append("Renuncia a derechos morales inviable en ES (LPI art. 14).")
    if "obras futuras" in clause_low:
        cons.append("Cesión de obras futuras indeterminada.")

    return {"pros": pros, "cons": cons}

def _devils_alt(flags: List[str], jurisdiction: str) -> Dict[str, Any]:
    """Construye una contra-lectura razonable en función de los riesgos detectados."""
    if "territorialidad ambigua" in flags:
        return {
            "hipotesis": "La explotación exige distribución global multi-plataforma.",
            "lectura": "Admitir 'worldwide' pero con sub-cláusula de precisión regional y mecanismos de takedown.",
            "cuando_mejor": "Cuando el cesionario asume obligaciones de reporting territorial y límites a sublicencia."
        }
    if "cesión futura genérica" in flags:
        return {
            "hipotesis": "Proyecto editorial continuado con entregas sucesivas pactadas.",
            "lectura": "Permitir cesión futura solo para obras claramente identificables en anexos/encargos.",
            "cuando_mejor": "Cuando existan PO/órdenes de trabajo con alcance, plazo y remuneración cerrados."
        }
    if "modalidades genéricas" in flags:
        return {
            "hipotesis": "Producto en rápida evolución tecnológica.",
            "lectura": "Enumeración abierta pero con 'familias' de soportes y derecho de revisión anual autor-editor.",
            "cuando_mejor": "Cuando se pacta reequilibrio (royalty) ante nuevos medios relevantes."
        }
    if "renuncia moral general" in flags and jurisdiction == "ES":
        return {
            "hipotesis": "Necesidad de edición/adaptación creativa de la obra.",
            "lectura": "No renuncia: consentimiento previo y por escrito para modificaciones sustanciales.",
            "cuando_mejor": "Siempre en ES (irrenunciable); en otros foros, limitar a usos concretos y salvaguardas."
        }
    # Por defecto, un contraste genérico
    return {
        "hipotesis": "Equilibrio entre seguridad del cesionario y derechos del autor.",
        "lectura": "Acotar soportes, plazo y territorio; remuneración proporcional cuando se amplíe el alcance.",
        "cuando_mejor": "Cuando el proyecto evoluciona por fases y se re-negocian extensiones."
    }

def draft_opinion(clause: str, jurisdiction: str, per_node: List[Dict[str, Any]], flags: List[str]) -> Dict[str, Any]:
    """Compone un dictamen estructurado usando solo las evidencias recuperadas."""
    # 1) Análisis con citas
    bullets = []
    for item in per_node:
        node = item["node"]
        retr = item["retrieval"]
        if retr["status"] != "OK":
            bullets.append(f"- {node['pregunta']}: **No concluyente** (falta evidencia con pinpoint).")
            continue
        tops = retr.get("citations", [])[:2]
        cites = "; ".join(_mk_cite(c["meta"]) for c in tops)
        sample = _slice(tops[0]["text"]) if tops else ""
        bullets.append(f"- {node['pregunta']}: {cites}\n  > {sample}")

    analysis = "### Análisis (regla → hechos → aplicación)\n" + "\n".join(bullets)

    # 2) Pros/Contras heurísticos
    pc = _pros_cons_from_clause(clause, jurisdiction)

    # 3) Contra-lectura (Devil’s Advocate)
    devil = _devils_alt(flags, jurisdiction)

    return {
        "analysis_md": analysis,
        "pros": pc["pros"],
        "cons": pc["cons"],
        "devils_advocate": devil
    }
