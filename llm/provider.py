import os, json
from typing import Any, Dict
from openai import OpenAI

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def get_client() -> OpenAI:
    # OPENAI_API_KEY viene del secreto del workflow
    return OpenAI()

def call_llm_json(system_instructions: str, payload: Dict[str, Any], json_schema: Dict[str, Any], model: str | None = None) -> Dict[str, Any]:
    """
    1º intenta Responses API con Structured Outputs (si tu SDK lo soporta).
    Si no, hace fallback a Chat Completions con response_format=json_object.
    Siempre devuelve un dict JSON válido o una salida 'No concluyente' segura.
    """
    client = get_client()
    model = model or DEFAULT_MODEL

    # ---- PRIMER INTENTO: Responses API (Structured Outputs) ----
    try:
        resp = client.responses.create(
            model=model,
            instructions=system_instructions,
            input=json.dumps(payload, ensure_ascii=False),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("name", "StructuredOutput"),
                    "schema": json_schema["schema"],
                    "strict": True
                },
            },
        )
        text = getattr(resp, "output_text", None)
        if text:
            return json.loads(text)
    except TypeError:
        # SDK antiguo: no soporta response_format en Responses.create
        pass
    except Exception as e:
        # Si falla por otra razón, seguimos al fallback
        pass

    # ---- FALLBACK: Chat Completions con JSON estricto ----
    try:
        chat = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system",
                 "content": (
                    "Eres un asistente jurídico de PI. Redacta SOLO en JSON válido, "
                    "sin texto fuera del JSON, siguiendo exactamente este esquema: "
                    f"{json.dumps(json_schema['schema'], ensure_ascii=False)}"
                 )},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        content = chat.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        # Último recurso: salida segura No concluyente
        return {
            "analysis_md": f"### Análisis\nNo concluyente: error al invocar LLM ({type(e).__name__}).",
            "pros": [],
            "cons": [],
            "devils_advocate": {"hipotesis": "—", "lectura": "—", "cuando_mejor": "—"}
        }
