# LexDomus–PI — MVP (RAGA+MCP)

**Objetivo:** asistente jurídico deliberativo para cesión/licencia de DPI con trazabilidad (EEE-Gate v2), RAG híbrido y políticas de gobernanza (AI Act).

## Módulos
- **verdiktia/**: descomposición y deliberación (Planner / Devil’s Advocate).
- **lex_domus/**: RAG híbrido (BM25+denso+rerank) con filtros de `policy.yaml`.
- **metrics_eee/**: EEE-Gate v2 (T, J, P + claridad de cita + ambigüedad) y *logs* JSONL encadenados.
- **ui/**: app Streamlit (3 vistas: Inquiry Graph · Comparativa+fuentes · Cláusula+EEE+A2J).
- **policies/**: `policy.yaml` (fuentes, vigencia, jurisdicción, privacidad).
- **prompts/**: plantillas de *prompting* por agente.
- **templates/**: plantillas de cláusula y resumen A2J.
- **data/**, **indices/**: corpus e índices.
- **tests/**: pruebas básicas.

## Arranque rápido (si decides ejecutarlo)
```bash
pip install -r requirements.txt
streamlit run ui/streamlit_app.py
