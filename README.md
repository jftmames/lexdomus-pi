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

Métricas objetivo (V1)

Cobertura citada ≥ 90%

EEE: T≥4.5, J≥4.0, P≥4.0 (sobre 5)

p95 latencia ≤ 12 s (índice local)

0 PII/biométrico en muestreo de 1.000 outputs


---

# 3) Políticas de gobernanza

### 3.1 `policies/policy.yaml`
**Path:** `policies/policy.yaml`
```yaml
version: 1.0
updated: 2025-10-13

ai_act:
  risk_class: "limited"
  human_oversight: true
  transparency_notice: true

sources:
  allowed:
    - "BOE"
    - "EUR-Lex"
    - "WIPO/OMPI"
    - "USC (Cornell/LII)"
  denied:
    - "wikis no oficiales"
    - "blogs sin revisión"
    - "datasets con imágenes personales"

temporal_vigency:
  snapshot_mode: true
  min_publication_year: 1990
  warn_on_amendments: true

jurisdictions: ["ES","EU","US","INT"]

privacy:
  block_personal_data: true
  block_biometrics: true
  pre_index_filters: ["faces","signatures","emails","phones","addresses"]
  pre_prompt_sanitization: true
  deny_on_privacy_violation: true

rag:
  retrieval:
    top_k: 8
    hybrid: true           # BM25 + denso
    hyde: true
    rerank: "cross-encoder"
  thresholds:
    min_citations: 2
    require_pinpoint: true # art./apartado/párrafo
  generation:
    source_required: true  # sin fuentes -> 'No concluyente'
    max_context_chars: 12000

eee_gate:
  min_T: 4.5
  min_J: 4.0
  min_P: 4.0
  enforce_no_conclusion_if_insufficient: true
  penalize_vague_citations: true

logging:
  jsonl_chain: true
  hashing: "sha256"
  redact_pii_preview: true
