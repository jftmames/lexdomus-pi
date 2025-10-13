# app/writer_llm.py
import os, json, textwrap
from typing import Any, Dict, List

def _schema() -> Dict[str, Any]:
    # Esquema esperado para validar mínimamente la salida
    return {
        "type": "object",
        "properties": {
            "analysis_md": {"type": "string"},
            "pros": {"type": "array", "items": {"type": "string"}},
            "cons": {"type": "array", "items": {"type": "string"}},
            "devils_advocate": {
                "type": "object",
                "properties": {
                    "hipotesis": {"type": "string"},
                    "lectura": {"type": "string"},
                    "cuando_mejor": {"type": "string"},
                },
                "required": ["hipotesis", "lectura", "cuando_mejor"],
            },
        },
        "required": ["analysis_md", "pros", "cons", "devils_advocate"],
    }

def _gather_citations(per_node: List[Dict[str, Any]], max_per_node: int = 2):
    cites = []
    idx = 1
    for item in per_node:
        retr = (item or {}).get("retrieval", {})
        for c in (retr.get("citations") or [])[:max_per_node]:
            meta = c.get("meta", {})
            cites.append({
                "id": idx,
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "jurisdiction": meta.get("jurisdiction", ""),
                "ref": meta.get("ref_label", ""),
                "url": meta.get("ref_url", ""),
                "pinpoint": bool(meta.get("pinpoint", False)),
                "lines": [meta.get("line_start"), meta.get("line_end")],
                "text": c.get("text", ""),
            })
            idx += 1
    return cites

def _heuristic_analysis(clause: str, jurisdiction: str, per_node, flags) -> Dict[str, Any]:
    # Ensambla un análisis mínimo usando las citas presentes
    cites = _gather_citations(per_node, max_per_node=2)
    bullets = []
    for ci in cites:
        tag = f"[{ci['id']} {ci['jurisdiction']} {ci['ref']}]".strip()
        pin = " (pinpoint)" if ci.get("pinpoint") else ""
        bullets.append(f"- {tag}{pin}: {ci['text'][:280].strip()}…")
    body = "\n".join(bullets) if bullets else "_No hay evidencia textual suficiente en las citas recuperadas._"

    # Pros/Contras básicos a partir de flags
    pros, cons = [], []
    if "renuncia moral general" in (flags or []):
        cons.append("Pretende renunciar a derechos morales que son irrenunciables en varias jurisdicciones (p. ej., LPI art. 14; Berna art. 6bis).")
        pros.append("Aclara posibilidad de modificaciones por el cesionario (siempre que no lesionen integridad).")
    if not cons:
        cons.append("Revisar concreción de modalidades, territorio y plazo.")
    if not pros:
        pros.append("Hay base para negociar una licencia limitada y respetuosa con derechos morales.")

    analysis = textwrap.dedent(f"""
    **Cláusula analizada (jurisdicción: {jurisdiction})**

    {clause}

    **Lectura guiada por evidencia**
    {body}

    **Notas**
    - Usa solo la evidencia citada y normas explícitas.
    - Los derechos morales son, como regla, irrenunciables; cabe autorizar ciertos actos sin menoscabar paternidad ni integridad.
    """).strip()

    return {
        "analysis_md": analysis,
        "pros": pros[:5],
        "cons": cons[:5],
        "devils_advocate": {
            "hipotesis": "El cesionario necesita flexibilidad de edición/versión.",
            "lectura": "Autoriza ajustes técnicos razonables sin afectar paternidad ni integridad; no hay renuncia general.",
            "cuando_mejor": "Cuando se listan límites claros (p. ej., correcciones de formato) y se exige atribución.",
        },
    }

def draft_opinion_llm(clause: str, jurisdiction: str, per_node: List[Dict[str, Any]], flags: List[str]) -> Dict[str, Any]:
    """
    Devuelve un dict con: analysis_md, pros, cons, devils_advocate.
    Intenta LLM si USE_LLM=1 y hay OPENAI_API_KEY; si falla, usa heurístico.
    """
    use_llm = os.getenv("USE_LLM", "0") == "1" and bool(os.getenv("OPENAI_API_KEY", "").strip())
    cites = _gather_citations(per_node, max_per_node=2)

    if not use_llm:
        return _heuristic_analysis(clause, jurisdiction, per_node, flags)

    # --- Construcción de prompt estructurado ---
    system = (
        "Eres asistente jurídico especializado en propiedad intelectual. "
        "Escribe únicamente a partir de la EVIDENCIA proporcionada (citas) y la cláusula, "
        "sin inventar normas ni hechos. Devuelve un JSON válido con las claves: "
        "analysis_md (markdown), pros (lista), cons (lista), devils_advocate {hipotesis, lectura, cuando_mejor}."
    )

    payload = {
        "jurisdiction": jurisdiction,
        "clause": clause,
        "flags": flags or [],
        "citations": cites,
        "instructions": [
            "Usa referencias en texto como [n] donde n es el id de la cita.",
            "Si la evidencia es insuficiente, indícalo claramente en analysis_md.",
            "Pros/Contras: máximo 5 ítems; frases breves, accionables.",
            "Devil’s Advocate: propone una lectura alternativa razonable, no caricaturesca.",
            "Responde SOLO con JSON. Sin texto fuera del JSON."
        ],
        "schema": _schema(),  # para información del modelo; no es validado automáticamente
    }

    try:
        # Llamada al proveedor
        from llm.provider import call_llm_json
        out = call_llm_json(system, payload, _schema())
        # Sanea mínima estructura
        if not isinstance(out, dict):
            raise ValueError("Respuesta LLM no es dict")
        if "analysis_md" not in out:
            # compatibilidad con 'analysis'
            if "analysis" in out:
                out["analysis_md"] = out["analysis"]
        # Asegura tipos
        out["pros"] = [str(x) for x in (out.get("pros") or [])][:5]
        out["cons"] = [str(x) for x in (out.get("cons") or [])][:5]
        dev = out.get("devils_advocate") or {}
        if not isinstance(dev, dict):
            dev = {"hipotesis": str(dev), "lectura": "-", "cuando_mejor": "-"}
        out["devils_advocate"] = {
            "hipotesis": dev.get("hipotesis", "-"),
            "lectura": dev.get("lectura", "-"),
            "cuando_mejor": dev.get("cuando_mejor", "-"),
        }
        return out
    except Exception:
        # Cualquier fallo → regreso heurístico
        return _heuristic_analysis(clause, jurisdiction, per_node, flags)
