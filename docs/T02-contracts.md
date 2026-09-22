# T02 — preguntas y procedencia de las citas

Cambio limitado sobre la línea de base `f9591bbdb3482cbe6e9a3868300b10a5bfcc25d4`.
Comprobación local: 9 de septiembre de 2026, Python 3.11.16.

## Problema y comportamiento corregido

El motor Inquiry produce `pregunta`, pero el pipeline buscaba `question` y
recuperaba con una consulta que empezaba por `None`. La ingesta escribe
metadatos planos, mientras el recuperador buscaba sólo `meta`: las citas
perdían su documento, fuente y enlace. Además, los reintentos del pipeline
podían terminar recuperando candidatos sin aplicar la política.

- `pregunta` sigue siendo el campo canónico, compatible con el productor y el
  redactor alternativo. El consumidor exige una pregunta no vacía; los fallos
  de Inquiry y RAG se propagan sin inventar preguntas ni omitir la política.
- `lex_domus/contracts.py` define la estructura de una cita. Acepta registros
  planos o anidados y conserva sus campos bajo `meta`, incluido `doc_id`.
  Excluye registros incompletos, incoherentes o con URL mal formada. No
  rellena procedencia ni fabrica referencias.
- La lista de fuentes admitidas se aplica antes de seleccionar los primeros
  candidatos. Una política explícita vacía o mal formada no autoriza fuentes
  y no se sustituye por la política de respaldo.
- El redactor conserva también `doc_id`. Este primer bloque mantuvo los
  estados internos `OK` / `NO_EVIDENCE`. La evolución posterior de la API
  y su interfaz se documenta en [T02-api-v0.2.md](T02-api-v0.2.md).
- CI ejecuta las regresiones en push y pull request, con permisos de lectura,
  `USE_LLM=0`, clave vacía y sin nuevas dependencias de pruebas.

Estas comprobaciones son estructurales: una URL con formato correcto y una
etiqueta de fuente admitida no demuestran autenticidad, vigencia ni relevancia
jurídica de su contenido.

## Efectos esperados sobre el corpus actual

De 870 registros, 657 conservan la identidad mínima exigida. Se excluyen 213
registros BOE sin `ref_url`; se mantienen en el corpus para su reparación, no
se eliminan archivos ni se inventan enlaces.

Con la política de respaldo actual hay 407 registros estructuralmente
elegibles. Otros 250 utilizan `WIPO/OMPI` o `USC (Cornell/LII)`, que no coinciden
con `WIPO` y `USC` de esa política. Este cambio no crea equivalencias ni amplía
la lista de fuentes. Una política explícita diferente cambia la selección.

La falta de `policy.yaml`, las etiquetas y la política jurídica versionada
siguen pendientes de T04. `NO_EVIDENCE` puede expresar exclusión por política
o falta de procedencia; todavía no distingue todos los motivos.

## Validación

```bash
USE_LLM=0 python -m unittest discover -s tests -p 'test_contracts.py' -v
USE_LLM=0 python -m tests.smoke
```

Los 16 tests de contrato usan corpus temporal sintético, bloquean conexiones
de red y comprueban que no se llame al proveedor real. Cubren preguntas,
propagación de errores, procedencia hasta el redactor, formatos plano/anidado,
conflictos, URLs inválidas, política vacía y candidatos no autorizados que no
deben desplazar al autorizado del límite de resultados.

Resultado local: 16/16 regresiones; 10/10 casos smoke existentes; `pytest`
ejecuta 17 pruebas satisfactorias (las 16 nuevas y la prueba anterior).

Al repetir el diagnóstico de T01, B03 pasa de consultas `None` a las dos
preguntas del productor. B04 pasa de 12 citas sin metadatos a 12 con metadatos
y `doc_id`. Los restantes criterios de ese diagnóstico no cambian. Ninguna
de estas cifras mide precisión jurídica ni acredita uso profesional.

## Pendiente

Este bloque no autoriza expedientes reales. La continuación
[T02-api-v0.2.md](T02-api-v0.2.md) incorpora entrada estricta, límites, estados,
interfaz y omisión de generación ante ausencia total de evidencia. Siguen
pendientes política jurídica, pérdida de líneas en ingesta, coherencia de
índices, negaciones y alternativas, suficiencia jurídica para abstención,
registro de trazabilidad, identificación del motor, seguridad y validación
del despacho.

No se ha actualizado el corpus, cambiado dependencias ni ejecutado modelos
reales. La integración existente de Vercel crea previews automáticas de la PR;
no se ha promovido el cambio a producción. La propuesta requiere revisión
antes de integrarse en `main`.
