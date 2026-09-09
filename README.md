# LexDomus-PI — prototipo de apoyo a la revisión jurídica

API FastAPI e interfaz Next.js para explorar cláusulas de cesión y licencia
de propiedad intelectual. El piloto propuesto se limita a cláusulas editoriales
bajo jurisdicción española y a textos sintéticos. **No está habilitado para
expedientes reales ni sustituye la revisión de un abogado.** El despacho aún
debe aceptar el alcance y validar los resultados.

Esta rama incorpora el bloqueo de [T04.1](docs/T04-policy.md): la política de
fuentes está pendiente de revisión y `/analyze` devuelve **503**. Es el resultado
esperado, también con `USE_LLM=0`. Las pruebas usan políticas ficticias sobre
datos sintéticos; no conviertas esas políticas de prueba en configuración de uso.

## Arranque local

Entorno de referencia: Linux x86_64, Python **3.11.16** (`.python-version`),
Node **24.19.0** (`web/.nvmrc`) y npm **11.9.0**.
Ejecuta desde la raíz del repositorio:

```bash
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.api.txt
.venv/bin/python -m pip check
USE_LLM=0 .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

En otra terminal, con la versión indicada de Node:

```bash
cd web
npm ci --no-audit --no-fund
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

Abre <http://localhost:3000>. La documentación de la API está en
<http://localhost:8000/docs>. `USE_LLM=0` utiliza el modo simulado y no requiere
clave ni consume llamadas de pago. No introduzcas datos de clientes.
En otros sistemas usa el contenedor de desarrollo o adapta la activación del
entorno; la resolución de Python se ha validado en la plataforma indicada.

## Contrato y límites

`POST /analyze` admite `clause` (1–5.000 puntos de código Unicode, no sólo
blancos) y `jurisdiction: "ES"`. La respuesta contractual es versión `0.2`.
Devuelve un borrador que exige revisión o `INSUFFICIENT_EVIDENCE`; sin citas
admisibles no ejecuta la generación. Tener alguna cita **no acredita suficiencia
jurídica, autenticidad ni vigencia**. Véase [el contrato](docs/T02-api-v0.2.md).

`GET /health` informa del proceso y de la existencia de archivos; no certifica
integridad del corpus ni disponibilidad jurídica. Siguen pendientes la aprobación
y saneamiento de fuentes, consistencia de índices, negaciones,
trazabilidad persistente, autenticación y límites de transporte/frecuencia.
El CORS actual es de demostración. No expongas esta API como servicio público.

Una interfaz remota exige `NEXT_PUBLIC_API_BASE` explícita en la compilación.
Las previews de Vercel no validan ni despliegan por sí mismas el backend.

## Verificación técnica sin proveedores

```bash
USE_LLM=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -v
USE_LLM=0 .venv/bin/python -m tests.smoke
USE_LLM=0 .venv/bin/python -m tests.ingestion_smoke
.venv/bin/python scripts/ingest.py --check
.venv/bin/python tools/dependency_inventory.py --check
npm --prefix web test
npm --prefix web run typecheck
npm --prefix web run build
```

La batería comprende 85 regresiones Python, 10 casos del detector de flags y 10 pruebas de
interfaz. No mide precisión jurídica ni demuestra adopción por el despacho.
Los casos heredados `tests.smoke` comprueban exclusivamente flags; las pruebas
de contrato y API ejercitan el pipeline real con fixtures y bloqueo de red.
`tests.ingestion_smoke` construye un candidato sintético y su índice BM25 en
un directorio temporal, sin modificar los datos activos.

## Ingesta de candidatos

[T05](docs/T05-ingestion.md) sustituye la detección por nombre de archivo por
un registro explícito: `policies/corpus-registry.json`. Las 14 copias actuales
están en cuarentena por los motivos documentados; ninguna está aprobada.
La fragmentación conserva el texto tras normalizar únicamente saltos de línea.

Una futura ingesta exige política y documentos revisados, hashes coincidentes
y `--output-dir` explícito. Produce un directorio nuevo con `chunks.jsonl` y
`manifest.json`. **No publica ni sustituye `data/docs_chunks` o `indices`.**
No copies una política de tests para habilitar datos reales.

Los cinco workflows heredados que llaman a `ingest.py` sin destino quedan
bloqueados por esa invocación incompatible. Deben adaptarse a la selección y
promoción explícita de candidatos en T13 antes de fusionar esta propuesta.
CI ya utiliza un corpus sintético aislado para verificar ingesta e índice.

## Componentes y mantenimiento

- `api/`: límites HTTP y esquemas; `web/`: interfaz actual.
- `app/`, `verdiktia/`, `lex_domus/`: pipeline, preguntas y recuperación.
- `data/`, `indices/`: corpus e índices de demostración, pendientes de saneamiento.
- `requirements.api.txt`: bloqueo completo de API y núcleo con hashes.
  `requirements.txt`: bloqueo del núcleo para tareas de corpus; no instala la API.
- `web/package-lock.json`: bloqueo de dependencias de interfaz y compilación.
- `Dockerfile`: imagen de API no-root; `.devcontainer/`: desarrollo Python/Node.

La [revisión T03](docs/T03-dependencies.md) documenta actualización, auditorías,
reproducción y reversión. El [inventario y licencias](docs/dependencies/README.md)
incluye un SBOM CycloneDX; no equivale a una auditoría jurídica de licencias.
Los workflows de mantenimiento conservan limitaciones documentadas en T03.

Este repositorio aporta evidencia técnica de desarrollo. La transferencia de
conocimiento requiere además uso real documentado, validación del destinatario
y resultados; no se afirma que el software por sí solo acredite méritos ANECA.
