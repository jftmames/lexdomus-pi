# T13.1 — preparación sintética aislada; mantenimiento real suspendido

Propuesta sobre T06 (`d44ef0d`), sin fusionar ni activar fuentes reales.

## Comportamiento

`build-index.yml` ejecuta el ensayo CLI de T06: ingesta en un directorio nuevo,
preparación contrastada con originales ficticios, selección del identificador en
el proceso de prueba y consulta con comprobación de procedencia. Rechaza una
política pendiente antes de crear el destino y un identificador incorrecto antes
de consultar. Las conexiones de red y la llamada al proveedor están bloqueadas
durante el ensayo (la instalación de dependencias de CI sí requiere red).

El artefacto `synthetic-snapshot-<run>-<attempt>` contiene snapshot, originales
ficticios, registro/política de prueba, aviso y `evidence.json` con identificadores,
hashes y resultados. Se conserva siete días. Sólo se sube si el ensayo termina
correctamente. No contiene configuración de activación ni secretos. La política
sintética NO acredita revisión de fuentes reales y nunca debe copiarse para
habilitarlas. Los hashes comprueban integridad, no constituyen aprobación.

El workflow sólo tiene `contents: read`; checkout no conserva credenciales.
Se ejecuta manualmente y en push/PR para los archivos relevantes. No escribe
commits, descarga normativa, cambia baseline, promociona ni llama a modelos.
El nombre de archivo se mantiene por continuidad; no construye BM25/FAISS.

`fetch-corpus.yml`, `post-reforms-merge.yml`, `llm-preview.yml` y `llm-eval.yml`
quedan exclusivamente manuales, sin permisos, checkout, secretos ni inputs. Su
único paso explica la suspensión y termina con error. No se presenta una ejecución
suspendida como evaluación superada. Se retiran cron y promoción post-merge.
Esto sólo tendrá efecto en las ramas que incorporen este cambio: no desactiva
los workflows actuales de `main` ni cambia la configuración alojada.

## Verificación

```bash
python -m unittest discover -s tests -p 'test*.py'
python -m tests.ingestion_smoke --output-dir /tmp/new-synthetic-evidence
python scripts/ingest.py --check
python tools/evaluate_retrieval.py --check
```

El destino de exportación debe ser nuevo. Tres regresiones adicionales comprueban
el contenido y hashes del artefacto, la negativa a sobrescribir y la ausencia de
exportación cuando falla la preparación. La batería inicial sumaba 102 pruebas Python; la adaptación del evaluador añade
ocho regresiones y eleva el total a 110.
El smoke original sin argumentos conserva su funcionamiento temporal.

## Pendientes para cerrar T13

- Descargas aisladas y revisión explícita de candidatos reales.
- Promoción y reversión autorizadas que vinculen política, registro, snapshot e
  identificador seleccionado; conflictos deben detener la operación.
- Migración operativa de los workflows preview/eval. El evaluador mecánico ya
  consume el snapshot seleccionado y trata abstenciones; su workflow sigue
  suspendido hasta definir entradas y ejecución autorizadas. El script de preview
  todavía fuerza `USE_LLM=1`. No se habilitan proveedores con esta propuesta.
- Sustituir indicadores legacy de `family_trends`/`rebuild_summary` por evidencia
  del estado seleccionado cuando se habilite el mantenimiento real.

Las 14 copias siguen en cuarentena y la política real sigue pendiente. T13.1 no
cierra T07–T13, calidad jurídica, sinónimos, Vercel ni validación del despacho.
La PR #7 y la cadena de PR anteriores permanecen sin fusionar. Esta suspensión
explícita reduce riesgo operativo; no equivale a completar la migración funcional.

## Evaluador mecánico adaptado

`scripts/llm_eval.py` conserva su nombre histórico, pero ejecuta únicamente MOCK,
incluso si el proceso hereda `USE_LLM=1`. Restaura esa variable al terminar.
No reconstruye corpus y exige la selección T06 (`LEXDOMUS_SNAPSHOT_DIR` absoluto
y `LEXDOMUS_SNAPSHOT_ID`). La política y el registro se leen de las rutas ya
establecidas por el runtime. La política real pendiente sigue bloqueando su uso.
Las pruebas sustituyen esas rutas por fixtures temporales; el operador no recibe
una excepción a la política ni una aprobación sintética para fuentes reales.

```bash
python scripts/llm_eval.py --cases /ruta/casos-revisados.jsonl --output-dir /ruta/informe-nuevo
```

Cada línea JSON exige exactamente `id`, `jurisdiction` (ES), `clause`,
`expected_gate` (OK o NO_EVIDENCE) y `expected_flags` (lista explícita).
La lista completa se valida antes del análisis. Se rechazan conjuntos vacíos,
IDs repetidos, otras jurisdicciones y el formato legacy sin expectativas de gate.
`tests/casos_frontera.jsonl` se conserva para sus consumidores de flags; no se le
atribuyen expectativas de recuperación sin revisión.

El evaluador verifica el snapshot antes de procesar, exige el mismo contexto en
todas las respuestas y vuelve a comprobarlo antes de exportar. Una abstención
esperada cuenta como acierto; una recuperación inesperada o una ausencia cuando
se esperaba evidencia cuenta como fallo. Los flags deben coincidir exactamente.
EEE ausente en abstenciones queda nulo y se excluye de las medias, nunca se
sustituye por cero. Sin casos puntuados, las medias son nulas.

Se generan CSV y JSON sólo después de completar el análisis, en un directorio
nuevo. Incluyen hash de los casos, contexto de recuperación, resultados por ID,
aciertos y fallos separados y número de casos con EEE. No incluyen cláusulas,
texto de citas ni opiniones. Salidas: 0 todos los casos cumplen; 1 discrepancias
con informe; 2 error/bloqueo. No hay umbral del 60% que permita ocultar casos
fallidos. Los errores se muestran con mensaje fijo, sin detalles del expediente.

Esta evaluación mide coherencia mecánica de gate/flags. No mide pertinencia de
cada documento, suficiencia jurídica, calidad del redactor LLM ni fidelidad del
motor. Las ocho regresiones usan recuperación real sobre texto ficticio y
bloquean red/proveedor. Los workflows de evaluación y preview siguen suspendidos.
