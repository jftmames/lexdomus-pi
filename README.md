# LexDomus-PI — prototipo de apoyo a la revisión jurídica

API FastAPI e interfaz Next.js para explorar cláusulas de cesión y licencia
de propiedad intelectual. El piloto propuesto se limita a cláusulas editoriales
bajo jurisdicción española y a textos sintéticos. **No está habilitado para
expedientes reales ni sustituye la revisión de un abogado.** El despacho aún
debe aceptar el alcance y validar los resultados.

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
integridad del corpus ni disponibilidad jurídica. Siguen pendientes la política
de fuentes, pérdidas de ingesta, consistencia de índices, negaciones,
trazabilidad persistente, autenticación y límites de transporte/frecuencia.
El CORS actual es de demostración. No expongas esta API como servicio público.

Una interfaz remota exige `NEXT_PUBLIC_API_BASE` explícita en la compilación.
Las previews de Vercel no validan ni despliegan por sí mismas el backend.

## Verificación técnica sin proveedores

```bash
USE_LLM=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -v
USE_LLM=0 .venv/bin/python -m tests.smoke
.venv/bin/python tools/dependency_inventory.py --check
npm --prefix web test
npm --prefix web run typecheck
npm --prefix web run build
```

La batería comprende 39 regresiones Python, 10 casos smoke y 9 pruebas de
interfaz. No mide precisión jurídica ni demuestra adopción por el despacho.

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
