# T02 — contrato de `/analyze` para el piloto técnico

Revisión: 9 de septiembre de 2026. Continúa el bloque de preguntas y citas
descrito en [T02-contracts.md](T02-contracts.md). La definición ejecutable está
en `api/schemas.py` y su exportación en [openapi-analyze-v0.2.json](openapi-analyze-v0.2.json).

## Alcance y compatibilidad

El alcance propuesto al despacho es revisar cláusulas editoriales de cesión
o licencia bajo jurisdicción española. La interfaz se limita a pruebas con
texto sintético. El despacho aún debe aceptar el alcance y validar resultados.
La API comprueba jurisdicción y formato; no clasifica automáticamente si el
contenido pertenece a una cesión o licencia editorial.

Este contrato cambia la API anterior: exige `jurisdiction: "ES"`, no admite
campos adicionales y limita `clause` a 5.000 puntos de código Unicode,
incluidos espacios y saltos de línea. API e interfaz deben actualizarse juntas;
la interfaz rechaza respuestas antiguas sin `contract_version: "0.2"`.

```json
{"clause":"Cláusula editorial sintética para una prueba técnica.","jurisdiction":"ES"}
```

Se rechazan campos ausentes, tipos distintos de cadena, texto vacío o formado
sólo por blancos y Unicode con sustitutos aislados. El texto aceptado se
conserva exactamente, sin recortarlo ni normalizar su redacción. En Python se
cuentan caracteres con `len`; en JavaScript, con `Array.from(text).length`.
Un emoji no se cuenta dos veces. El criterio común de blancos comprende
`isspace()` de Python y BOM; en JavaScript equivale a
`/^[\s\u001c-\u001f\u0085]*$/u`.

## Estados observables

| HTTP | Estado | Comportamiento |
| --- | --- | --- |
| 200 | `DRAFT_REVIEW_REQUIRED` | Cada cuestión identificada tiene citas admisibles y hay un borrador no vacío; exige revisión profesional. |
| 200 | `INSUFFICIENT_EVIDENCE` | Ningún nodo recuperó citas admisibles. No se ejecutan redactor, alternativa ni EEE. |
| 422 | `INVALID_INPUT` | Entrada que incumple el contrato o JSON mal formado. No se inicia el pipeline. |
| 400 | `INVALID_INPUT` | Cuerpo que el servidor no puede interpretar, por ejemplo bytes UTF-8 inválidos. |
| 422 | `OUT_OF_SCOPE` | Jurisdicción expresada como cadena distinta de `ES`. No se inicia el pipeline. |
| 500 | `TECHNICAL_ERROR` | Fallo del pipeline o respuesta interna inválida; mensaje controlado sin detalles privados. |

La respuesta incluye versión e identificador UUID generado por el servidor.
En respuestas 200, `review_required` siempre vale `true`. La falta de evidencia
devuelve `engine: "NOT_RUN"`, `opinion: null`, `alternative_clause: null` y
`EEE: null`. Un resultado contradictorio entre citas, gate y estado, una
opinión vacía, números no finitos o Unicode no serializable producen un error
técnico controlado.

Los errores exponen sólo nombres de campo autorizados y códigos controlados:
no devuelven la cláusula, nombres arbitrarios de campos, trazas ni el mensaje
original de una excepción. El registro técnico de este límite contiene el
UUID y el tipo de excepción. El UUID no constituye un registro de auditoría
persistente ni prueba de revisión profesional.

## Interfaz

- Jurisdicción ES fija, contador Unicode y bloqueo de entradas inválidas.
- Etiquetas distintas para borrador, resultado simulado y evidencia insuficiente.
- Citas con documento, fuente, jurisdicción y enlace; enlaces HTTP(S) sin
  credenciales. Su formato válido no acredita autenticidad ni vigencia.
- No presenta la plantilla `node.alternativa` como recomendación. Ante falta
  de evidencia muestra las preguntas sin texto de opinión ni alternativa.
- No presenta EEE como certificación de calidad jurídica.
- Limpia resultados al editar o volver a enviar; cancela la petición anterior
  y descarta respuestas tardías para evitar atribuirlas a otro texto.
- Requiere `NEXT_PUBLIC_API_BASE` explícito en entornos remotos. Sólo
  `localhost` y `127.0.0.1` permiten el valor local `http://localhost:8000`.
  Sin configuración remota, el botón permanece deshabilitado. La variable
  se incorpora al compilar Next.js y requiere recompilación al cambiarla.

## Verificación reproducible

Con Python 3.11.16 y un entorno virtual aislado:

```bash
python -m pip install --require-hashes -r requirements.api.txt
USE_LLM=0 python -m unittest discover -s tests -p 'test*.py' -v
USE_LLM=0 python -m tests.smoke
```

Las regresiones de contrato y API usan datos sintéticos y temporales, bloquean
red y proveedor real, y comprueban ausencia de llamadas incluso cuando una
excepción pudiera capturarse. Incluyen integración ASGI con el pipeline real
para ambos resultados 200. La prueba de omisión comprueba también `USE_LLM=1`
con clave ficticia sin ejecutar el proveedor. Los casos smoke anteriores
verifican flags; no miden precisión jurídica ni equivalen a las regresiones.

Desde `web`, con Node 24.19.0 y npm 11.9.0:

```bash
npm ci --no-audit --no-fund
node --test tests/analyze-contract.test.cjs
npm run typecheck
npm run build
```

CI ejecuta las regresiones Python, los smoke, las pruebas de contrato y
renderizado de interfaz y su compilación. No se añaden dependencias de
producto ni librerías de pruebas en T02. La actualización posterior
[T03](T03-dependencies.md) fija dependencias directas y transitivas y añade
comprobación de tipos, inventario y construcción de contenedores a CI.

## Límites y siguiente revisión

La regla actual exige candidatos para todas las preguntas identificadas; no
demuestra suficiencia jurídica. T08 debe definir pertinencia, soporte y
abstención más allá de la mera presencia de citas. Los nodos sin evidencia
se señalan en la interfaz. La etiqueta `LLM` conserva la lógica heredada:
identificar fielmente proveedor, ejecución y fallback sigue pendiente en T09.

Siguen pendientes política jurídica y procedencia (T04), pérdidas de ingesta e
integridad de índices, negaciones y alternativas, trazabilidad persistente,
autenticación, CORS, límites de frecuencia y tamaño bruto del cuerpo HTTP,
readiness de `/health` y validación del despacho. El límite de 5.000 caracteres
se aplica después de leer el JSON; no sustituye un límite de bytes de transporte.

Este cambio aporta evidencia de desarrollo y verificación técnica. No acredita
adopción por una entidad, impacto de transferencia ni evaluación favorable de
ANECA. La propuesta sigue en una PR de borrador; las previews automáticas de
Vercel no validan el backend ni habilitan expedientes reales.

## Actualización: cobertura parcial

La generación requiere candidatos en todas las cuestiones identificadas. Si
alguna no tiene candidatos, se devuelve `INSUFFICIENT_EVIDENCE`, conservando las
citas parciales pero sin opinión, alternativa ni EEE. API y cliente rechazan
un borrador con cuestiones sin candidatos. Esta condición necesaria no acredita
pertinencia ni suficiencia jurídica de las citas, y no cierra T08. Sustituye la
regla temporal anterior de «alguna cita».
