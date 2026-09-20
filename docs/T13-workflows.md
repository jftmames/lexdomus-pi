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
exportación cuando falla la preparación. La batería suma 102 pruebas Python.
El smoke original sin argumentos conserva su funcionamiento temporal.

## Pendientes para cerrar T13

- Descargas aisladas y revisión explícita de candidatos reales.
- Promoción y reversión autorizadas que vinculen política, registro, snapshot e
  identificador seleccionado; conflictos deben detener la operación.
- Migración de preview/eval a snapshots seleccionados, piloto ES y evaluación
  de abstenciones. Los scripts heredados todavía fuerzan `USE_LLM=1`; el evaluador
  no trata `EEE=None` correctamente. Permanecen suspendidos.
- Sustituir indicadores legacy de `family_trends`/`rebuild_summary` por evidencia
  del estado seleccionado cuando se habilite el mantenimiento real.

Las 14 copias siguen en cuarentena y la política real sigue pendiente. T13.1 no
cierra T07–T13, calidad jurídica, sinónimos, Vercel ni validación del despacho.
La PR #7 y la cadena de PR anteriores permanecen sin fusionar. Esta suspensión
explícita reduce riesgo operativo; no equivale a completar la migración funcional.
