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

`fetch-corpus.yml`, `reforms-watch.yml`, `post-reforms-merge.yml` y `llm-preview.yml`
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
ocho regresiones; tres más verifican su exportación en CI. Se añaden seis pruebas de descarga aislada. Total actual: 119.
El smoke original sin argumentos conserva su funcionamiento temporal.

## Pendientes para cerrar T13

- Descargas aisladas y revisión explícita de candidatos reales.
- Promoción y reversión autorizadas que vinculen política, registro, snapshot e
  identificador seleccionado; conflictos deben detener la operación.
- Migración operativa de los workflows preview/eval. El evaluador mecánico ya
  consume el snapshot seleccionado y trata abstenciones; su workflow sólo ejecuta
  el conjunto sintético fijo. La evaluación de fuentes reales sigue bloqueada. El script de preview
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
bloquean red/proveedor. El workflow de preview sigue suspendido. La evaluación automática sólo admite
el conjunto sintético fijo descrito a continuación.

## Workflow de evaluación sintética

`llm-eval.yml` ejecuta `tests.evaluation_smoke` en push/PR para archivos relevantes
y manualmente sin inputs de cláusula, modelo, corpus ni casos. Usa permisos de
lectura, checkout sin credenciales persistentes y no recibe secretos. Primero
comprueba las regresiones del evaluador y su exportación; después prepara un
snapshot temporal ficticio y evalúa `tests/fixtures/evaluation_synthetic.jsonl`.

Los dos casos declarados son una coincidencia literal (`zafiroqwerty`) y una
abstención (`inexistenteqwerty`). El original sintético contiene únicamente el
primer término. Son controles mecánicos deliberadamente mínimos: no simulan
un contrato ni evalúan pertinencia jurídica o sinónimos. No sustituyen la
batería T06 ni sus límites conocidos.

Durante preparación y evaluación se bloquean conexiones de red y proveedor.
Las rutas de política/registro se sustituyen sólo dentro del harness de tests
por fixtures temporales, sin alterar la política del repositorio. Antes de
exportar se comprueban 2/2 casos, una abstención correcta, un caso con EEE,
identificador del snapshot y hash del conjunto de casos. Una discrepancia o
bloqueo impide exportar. El destino debe ser nuevo.

El artefacto `synthetic-evaluation-<run>-<attempt>` contiene CSV, JSON y aviso.
Incluye `synthetic_only: true`, `activated: false`, cero llamadas externas,
hash del original ficticio, hash de casos y contexto del snapshot. No incluye
cláusulas, citas, políticas de prueba ni configuración de activación. El upload
se ejecuta sólo tras éxito y conserva el informe siete días. Una instalación
de dependencias de CI sí requiere red; el bloqueo se refiere al ensayo.

```bash
python -m tests.evaluation_smoke --output-dir /tmp/new-synthetic-evaluation
```

Esto conecta el evaluador mecánico a CI; no habilita evaluación profesional ni
promoción del corpus. Las ejecuciones alojadas en main no cambian hasta integrar.

## Descarga aislada para revisión

`scripts/fetch_corpus.py` ya no escribe en `data/corpus` ni genera extractos. No
hace nada al importarse y rechaza invocaciones antiguas sin argumentos. Requiere
un plan JSON explícito y un directorio absoluto nuevo fuera del repositorio,
cuyo padre exista. Formato del plan: `purpose: download_for_review` y `sources`,
una lista de objetos con `id` y `url`. No incluye un plan de fuentes reales
preaprobado. La lista admite de 1 a 20 entradas, IDs únicos y seguros, y HTTPS
en los cuatro hosts exactos del descargador anterior; no sigue redirecciones.
Esto limita destinos técnicos, NO aprueba identidad, reutilización o vigencia.

```bash
python scripts/fetch_corpus.py --plan /ruta/plan-revisado.json --output-dir /ruta/nueva-descarga
```

Conserva el cuerpo HTTP descargado sin extracción de texto en archivos `.body`,
con hash, tamaño, URL solicitada, tipo de contenido y fecha UTC en
`download-manifest.json`. Sólo admite HTTP 200, tipos documentales previstos y
hasta 8 MiB por documento; no hereda proxies ni credenciales netrc. Una descarga
vacía, error, redirección o exceso de tamaño elimina el lote creado en esa
invocación. Nunca sobrescribe un destino existente. Todo queda `unreviewed` y
`activated: false`; no produce candidatos T05 ni snapshots T06. La normalización,
identificación documental, revisión y admisión posterior siguen pendientes.

Se descubrió además `reforms-watch.yml`, que llamaba al descargador y podía
escribir status/proposed y abrir PR automáticamente. Se suspende antes de esos
pasos, sin cron ni permisos. `fetch-corpus.yml` también sigue suspendido: esta
fase valida el CLI con HTTP simulado, sin descargar normativa real. Los seis
tests cubren bytes/manifiesto, destinos existentes, rechazo de escritura en el
repositorio, URLs/IDs inválidos, respuestas fallidas y limpieza de lotes parciales.
