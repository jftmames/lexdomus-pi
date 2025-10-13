# llm/provider.py
import os, json, re
from typing import Any, Dict

_JSON_RE = re.compile(r"\{.*\}", re.S)

def get_client():
    # Cliente OpenAI moderno; permite usar base URL si la defines
    from openai import OpenAI
    base = os.getenv("OPENAI_BASE_URL")
    if base:
        return OpenAI(base_url=base, api_key=os.environ["OPENAI_API_KEY"])
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def _extract_json(text: str):
    if not text:
        return None
    m = _JSON_RE.search(text)
    if not m:
        return None
    s = m.group(0)
    try:
        return json.loads(s)
    except Exception:
        # intento de saneo básico de comillas
        s2 = s.replace("\n", "\\n")
        try:
            return json.loads(s2)
        except Exception:
            return None

def call_llm_json(system: str, payload: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envía instrucciones y contexto, y devuelve un dict (JSON) según schema esperado.
    No usa response_format; obliga al modelo por prompt y extrae el JSON del texto.
    """
    client = get_client()
    # Prompt compacto
    user = (
        "Devuelve SOLO JSON. Sigue el siguiente schema aproximado. "
        "Si no puedes completar alguna clave, pon '-'.\n\n"
        f"[SCHEMA]\n{json.dumps(schema)}\n\n"
        f"[PAYLOAD]\n{json.dumps(payload, ensure_ascii=False)}"
    )

    # Preferimos Responses API, pero sin response_format
    try:
        resp = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        )
        text = resp.output_text
    except Exception:
        # Fallback a chat.completions si la lib no trae Responses
        chat = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        )
        text = chat.choices[0].message.content

    data = _extract_json(text or "")
    if not isinstance(data, dict):
        raise ValueError("No se pudo extraer JSON de la respuesta del modelo")
    return data

