# T06 — recuperación sobre un snapshot verificado

9 de septiembre de 2026. Base: `7dc5cceb43fff5c3b4db3c73a23d15e3fe9c6b0d`
(PR #6, T05). Propuesta técnica en borrador para el piloto ES.

## Problema y decisión técnica

La ruta efectiva de `/analyze` reabría `chunks.jsonl` en cada consulta. Cada nodo
podía realizar dos intentos, de modo que un cambio entre consultas podía mezclar
copias dentro de una respuesta. Los índices BM25/FAISS no se utilizaban, aunque
la construcción y `/health` mostraban esos artefactos. Un JSON corrupto se
omitía y podía presentarse como ausencia de evidencia.

Se mantiene el algoritmo mínimo de coincidencia léxica, identificado como
`lexical-overlap-v1`. Extrae palabras mediante `\w+` Unicode y minúsculas; puntúa
el número de palabras distintas compartidas con la consulta. No elimina palabras
frecuentes, no resuelve sinónimos y no determina relevancia jurídica. Los empates
mantienen el orden del corpus. Los tokens se preparan una vez por análisis.

No se activa ningún índice persistente: `active_indices: []`. No se ha medido
una ventaja que justifique añadir BM25, FAISS o un índice de tokens en disco.
La API no declara recuperación híbrida. Los binarios heredados permanecen en
el historial/repositorio, pero quedan excluidos de la imagen y de la ruta de
recuperación. Un descriptor que declare cualquier índice activo es incompatible
con este modo y bloquea la carga; no se deserializa para averiguar su contenido.

## Preparación vinculada a originales

El candidato T05 contiene `chunks.jsonl` y `manifest.json`. La preparación:

1. Valida la política aprobada y el registro, sus hashes y revisiones.
2. Verifica hash e identidad del manifiesto, archivos y número de fragmentos.
3. Reconstruye cada documento normalizado por sus posiciones y regenera los
   fragmentos esperados, comprobando solapes, líneas, texto, identificadores,
   versiones, etiquetas y procedencia frente al registro.
4. Vuelve a ejecutar la ingesta desde los originales cuyos hashes coinciden con
   el registro. Exige igualdad exacta del candidato con ese resultado. Así no
   basta cambiar todo el texto y recalcular un manifiesto que conserve un hash
   original meramente declarado.
5. Escribe un directorio nuevo con esos dos archivos y `snapshot.json`. No
   modifica los candidatos anteriores, fuentes originales ni configuración activa.

El descriptor incluye esquema 1, modo, índices activos vacíos, `corpus_id`,
hashes de manifiesto y chunks y `snapshot_id`. Este último es SHA-256 del JSON
canónico del descriptor antes de añadir el propio campo. Se usa la serialización
T05: UTF-8, claves ordenadas, separadores compactos y salto final.

Se rechazan archivos adicionales en el candidato/snapshot, enlaces simbólicos,
entradas no regulares, JSON ambiguo o no canónico y archivos de más de 32 MiB.
Las lecturas de un snapshot comparten un descriptor de directorio para que un
renombrado no seleccione padres distintos a mitad de operación. Esta mecánica
está dirigida al entorno Linux de referencia; no se declara portabilidad nativa
de las operaciones `O_NOFOLLOW`/`dir_fd` a Windows.

## Selección y carga durante el análisis

La configuración debe seleccionar explícitamente:

| Valor | Significado |
| --- | --- |
| `LEXDOMUS_SNAPSHOT_DIR` | Ruta absoluta al directorio completo del snapshot |
| `LEXDOMUS_SNAPSHOT_ID` | Identificador exacto fijado fuera de ese directorio |
| `policies/corpus-registry.json` | Registro correspondiente a esa versión |
| `policies/policy.yaml` | Política revisada correspondiente a esa versión |

Cada petición carga la política y, antes de Inquiry, captura y verifica una sola
copia del snapshot. Comprueba el identificador configurado, el descriptor y
todas las relaciones de integridad del corpus con política/registro. No necesita
leer originales en producción: su correspondencia se comprobó al preparar;
la carga confía en la selección externa del identificador y vuelve a comprobar
estructura, hashes, política y registro. Alterar o reemplazar simultáneamente
todos los archivos no basta si no coincide el identificador seleccionado.

No se ofrece selección automática del candidato más reciente. T13 debe definir
el control de la aprobación, promoción y reversión. Quien pueda cambiar tanto
la configuración autorizada como el registro, política y archivos puede cambiar
el conjunto seleccionado; los hashes no son una firma ni un control de acceso.

El snapshot conserva citas serializadas y conjuntos de tokens inmutables. Todas
las consultas e intentos de una petición usan esa copia; cambiar los archivos
después de la carga no cambia la respuesta en curso. Una petición posterior
vuelve a cargar y verificar. Cada consulta devuelve objetos nuevos, de modo que
modificar una cita devuelta no altera consultas siguientes.

Las llamadas directas a `analyze_clause`, `source_required_answer` y
`retrieve_candidates` mantienen la comprobación obligatoria. No existe fallback
al corpus heredado, ni siquiera con `USE_LLM=0`. Los scripts de preview y
evaluación que llaman al pipeline heredan este comportamiento.

## Filtrado, duplicados y respuestas

La preparación rechaza documentos admitidos fuera de la política seleccionada.
La consulta mantiene además el filtro de fuentes antes de consumir el cupo `k`.
Dentro de una consulta, un texto idéntico del mismo documento y versión se
devuelve una sola vez; no desplaza referencias diferentes. Las copias distintas
y versiones documentales diferentes permanecen separadas. Esto no convierte
varias citas en prueba de suficiencia ni deduplica el soporte entre nodos: la
compuerta jurídica y el tratamiento global de evidencias siguen en T08.

Un corpus completo y válido sin coincidencias produce `NO_EVIDENCE` y la API
responde `INSUFFICIENT_EVIDENCE` sin generación. Un archivo ausente, alterado,
vacío, una versión desconocida, política/registro distintos o un índice declarado
incompatible produce `CorpusError`: `/analyze` devuelve 503 `TECHNICAL_ERROR`,
con identificador de petición y texto fijo, sin revelar cláusula, rutas ni detalles.

El contrato 0.2 añade `retrieval_context` con modo, `snapshot_id`, `corpus_id`
y `active_indices`. El pipeline siempre lo incluye. El esquema y la interfaz
aceptan respuestas anteriores sin contexto por compatibilidad; cuando está
presente exigen la procedencia T05 de todas las citas. No se muestran esos
detalles técnicos como una validación jurídica en la interfaz.

`/health` queda reducido a `{"status":"ok"}`: sólo informa de que el proceso
responde. Ya no enumera índices por existencia ni llama conectores. Es un cambio
de respuesta que debe tenerse en cuenta si se consumían esos campos. Readiness
integral, incluido registro protegido y otros controles de uso, sigue en T12.

## Ensayo y evidencia

```bash
USE_LLM=0 python -m tests.ingestion_smoke
USE_LLM=0 python -m unittest discover -s tests -p 'test*.py' -v
python tools/evaluate_retrieval.py --check
```

El ensayo recorre ingesta, preparación por CLI, carga fijada y consulta sobre
fixtures ficticios. Pasan 99 pruebas Python, 10 casos de flags, 11 pruebas de
interfaz, TypeScript y compilación de producción. Las pruebas cubren adulteración, mezcla de versiones,
ausencia de configuración, selección incompatible, aislamiento, negativa antes
de generación y conservación de metadatos hasta HTTP/redactor. Las regresiones
de componentes anteriores usan dobles explícitos de carga cuando su objeto es
Inquiry o el formato legacy; los tests de snapshots y las integraciones de API
usan archivos preparados y verificados de verdad.

La [evaluación reproducible](T06-evidence/retrieval.json) fija consultas y
respuestas esperadas exclusivamente sintéticas, identifica la versión y compara
con el escaneo léxico previo. Incluye límites de sinónimos y falta de soporte.
Resultado: 6 aciertos entre 7 consultas con documento esperado, una ausencia
correcta fuera del corpus y paridad de citas y orden en 8/8 con el escaneo previo.
La consulta «límite temporal» no encuentra el documento ficticio sobre plazo.
No es un conjunto de evaluación jurídica aprobado por el despacho. Ese conjunto
y la decisión sobre suficiencia siguen pendientes antes de uso profesional.

## Límites de integración

`scripts/build_index.py` conserva su nombre, pero ahora prepara un snapshot
léxico y exige `--candidate-dir` y `--output-dir`; los originales, registro y
política se indican con `--corpus-dir`, `--registry` y `--policy` cuando difieren
de los del repositorio. No construye BM25/FAISS ni descarga modelos. La selección
activa no se realiza por este comando.

Los cinco workflows heredados incompatibles con T05 siguen pendientes de T13;
sus llamadas a la construcción implícita de índices también deben adaptarse.
`family_trends` y los indicadores por existencia de `rebuild_summary` siguen
siendo informes sobre material heredado, no comprobaciones del corpus activo.
No deben usarse como evidencia de aptitud del piloto.

Las 14 copias reales siguen en cuarentena, la política está pendiente y no hay
snapshot real seleccionado. El trabajo no habilita expedientes reales ni cierra
T07–T13, el problema de previews Vercel o la validación del despacho. Esta fase
documenta la mecánica técnica; no acredita transferencia efectiva ni un mérito
ANECA por sí sola.

## Actualización posterior: evidencia por cuestión

La rama de integración elimina el reintento con la cláusula completa y exige
candidatos en cada nodo antes de generar. El recuperador activo y el formato de
snapshot no cambian. Los ensayos BM25/párrafos siguen siendo offline. Véase el
[expediente consolidado](INTEGRATION-REVIEW.md) para resultados y bloqueos, incluida
la limitación de Inquiry como plantilla fija.
