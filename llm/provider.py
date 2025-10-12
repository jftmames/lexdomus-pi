import os, json
from typing import Any, Dict
from openai import OpenAI

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def get_client() -> OpenAI:
    # OPENAI_API_KEY se inyecta como secreto del workflow
    return OpenAI()

def call_llm_json(system_instructions: str, payload: Dict[str, Any], json_schema: Dict[str, Any], model: str | None = None) -> Dict[str, Any]:
    """
    Llama a la Responses API con Structured Outputs (JSON Schema estricto).
    Devuelve un dict (ya parseado) o lanza excepción si no hay output válido.
    """
    client = get_client()
    model = model or DEFAULT_MODEL

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
    # SDK v1+ expone un helper output_text
    text = resp.output_text  # string con JSON válido
    return json.loads(text)
