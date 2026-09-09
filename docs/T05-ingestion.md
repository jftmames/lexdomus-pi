# T05 — conservación de texto y procedencia de candidatos

9 de septiembre de 2026. Base: `490de7650137ab502855c52e729aaff860aa6480` (T04.1).
Estado: propuesta técnica para revisión, sin corpus profesional aprobado.

## Problema y alcance resuelto

La ingesta anterior podía omitir líneas superiores al límite, eliminaba blancos
y líneas vacías y no introducía el solape anunciado. Deducía fuente y título
del nombre del TXT: un nombramiento judicial bajo `es_lpi.txt` entraba como LPI.
Una referencia general también podía marcarse como cita precisa.

Esta propuesta sustituye la detección por nombre por un registro de copias,
construye candidatos sin publicación y conserva las posiciones de cada fragmento.
No transforma el material heredado en normativa validada: la limpieza jurídica,
selección de versiones, permisos y revisión profesional siguen pendientes.

## Registro y cuarentena

`policies/corpus-registry.json` fija las 14 copias observadas con SHA-256 y motivo
individualizado. Todas tienen `state: quarantined` y `provenance: null`. Sus
archivos originales permanecen intactos; cuarentena significa exclusión de la
nueva ingesta, no borrado ni traslado. Los TXT no registrados también se excluyen
y aparecen en el informe del candidato, sin deducir autoridad por el nombre.

Una entrada `admitted` sólo es aceptada técnicamente si incluye:

- Identificador documental, título, fuente, jurisdicción, familia y URL explícita.
- Versión, fecha de versión, idioma, fecha de adquisición y tipo `normative_text`.
- Revisor, fecha y referencia de la decisión, más fundamento y referencia de
  revisión de reutilización. La revisión no puede preceder a versión/adquisición.
- Hash exacto del archivo disponible, UTF-8 válido y contenido no vacío; un BOM
  con blancos no cuenta como texto normativo. Se rechazan enlaces simbólicos,
  rutas que salgan del directorio y referencias incompletas.

La política de fuentes de T04 debe tener revisión registrada y admitir la fuente,
jurisdicción y host. Rellenar los campos no autentica al profesional, verifica
la decisión ni demuestra que el contenido sea normativa: son precondiciones
técnicas, sujetas a revisión y controles de acceso/trazabilidad posteriores.

## Conservación y localización

La única normalización es `CRLF`/`CR` a `LF`. Se conservan acentos, emoji, BOM,
espacios iniciales/finales y líneas vacías. Las ventanas tienen como máximo
1.000 puntos de código Unicode y comparten exactamente 120 cuando hay otra
ventana. Una línea larga se reparte; no se omite. El algoritmo siempre avanza.

Cada fragmento incluye `char_start` y `char_end`, intervalo cero-based con final
excluido sobre la copia normalizada, y líneas inclusivas que empiezan en uno.
Un salto de línea pertenece a la línea que termina. El texto del fragmento debe
coincidir exactamente con ese intervalo. La suma sin duplicar los solapes
reconstruye la copia normalizada completa. Los fragmentos de sólo blancos se
conservan para cobertura, pero el recuperador no los admite como evidencia.

`doc_id` identifica el documento declarado; `chunk_id` diferencia el fragmento
mediante SHA-256 de documento, versión, hash original e intervalo. Se conservan
`document_version`, `source_sha256` y `normalized_sha256`. Esta ampliación es
opcional para los registros heredados del contrato 0.2; cuando aparece, el grupo
de campos debe estar completo y sus posiciones y hashes ser válidos.

Los metadatos llegan a la recuperación, API y redactor. El contrato de interfaz
también rechaza procedencia parcial o posiciones incompatibles con el texto.
El redactor conserva la información en su entrada; no se añade una atribución
de validación jurídica al resultado. T10 debe convertir esa información en un
registro persistente protegido.

Las URLs provienen del registro. `ref_label` identifica documento y versión;
`pinpoint` queda en `false`: ni una expresión regular que encuentre «Artículo»,
ni el nombre de un fichero, acreditan un localizador jurídico preciso.

## Duplicados y manifiesto

Dos archivos sólo se colapsan si coinciden documento, versión, todos los campos
de procedencia y bytes originales. El manifiesto conserva el alias y el archivo
canónico elegido de forma determinista. Dos copias distintas que afirman la
misma identidad y versión causan bloqueo; no se escoge una silenciosamente.
Textos iguales de documentos o versiones diferentes permanecen separados.
Las repeticiones internas de un documento se conservan con sus posiciones.

El candidato contiene:

- `chunks.jsonl`: fragmentos deterministas con su procedencia.
- `manifest.json`: hash de los fragmentos, del registro y de la política,
  versiones, copias utilizadas, duplicados, cuarentena y cobertura por documento.

El hash de la política se calcula sobre su representación JSON canónica, no
sobre los bytes YAML. El hash del registro sí identifica sus bytes originales.
`corpus_id` es el hash del JSON canónico del manifiesto antes de añadir ese campo.
La serialización canónica ordena claves, usa separadores compactos, UTF-8 y un
salto final. Igual entrada y parámetros producen bytes idénticos; el nombre del
directorio candidato es temporal y no forma parte de esos hashes.

El manifiesto prueba correspondencia técnica con las copias y decisiones
declaradas. No es firma, sello de tiempo, prueba de autenticidad normativa ni
una defensa contra quien pueda modificar todos los archivos y sus hashes.

## Operación y efectos sobre automatismos

```bash
# Inspección sin construir ni promover; devuelve 2 si encuentra problemas de hash/archivo.
python scripts/ingest.py --check

# Ensayo completo sobre fixtures ficticios: candidato + construcción BM25 temporal.
USE_LLM=0 python -m tests.ingestion_smoke
```

La construcción requiere `--registry`, `--policy`, `--corpus-dir` cuando se usan
rutas diferentes de las del repositorio, y siempre `--output-dir` como directorio
padre de candidatos. Sólo tras validar se crea un directorio nuevo `candidate-*`.
No se sobrescribe ningún candidato existente, chunk activo o índice. Una
escritura fallida retira únicamente el candidato incompleto que acaba de crear.
La política y el registro actuales impiden construir candidatos de uso real.

**Incompatibilidad deliberada que impide fusionar sin adaptar los automatismos:**
`fetch-corpus.yml`, `build-index.yml`, `post-reforms-merge.yml`, `llm-preview.yml`
y `llm-eval.yml` siguen llamando a `python scripts/ingest.py` sin destino. Esa
invocación devuelve 2; no puede devolver éxito y luego construir un índice del
corpus anterior como si correspondiera al candidato nuevo. Su selección y
promoción deben rehacerse en T13, antes de integrar esta propuesta en `main`.

Las fases anteriores de esos workflows todavía pueden descargar o preparar
archivos en su runner antes de encontrar el bloqueo. No se han ejecutado ni
adaptado aquí, y la rama principal conserva sus ejecuciones existentes. La
restricción de adquisición y reutilización detectada para WIPO Lex sigue
requiriendo resolución expresa; no se ha hecho ninguna descarga jurídica.

CI de esta propuesta sustituye la reconstrucción sobre fuentes heredadas por
inspección del registro y un ensayo sintético de ingesta/BM25. No desactiva
las regresiones del pipeline o API. La imagen incluye únicamente el nuevo
script de ingesta, no los scripts de descarga de fuentes.

## Verificación y límites pendientes

85 pruebas Python: 48 de T04, 12 de fragmentación, 22 de ingesta y 3 de integración
con la API. Se comprueban reconstrucción exacta, solapes, offsets Unicode,
duplicados, hashes, versiones contradictorias, cuarentena, entradas inválidas,
aislamiento de escrituras y propagación hasta el redactor. Diez casos de flags
y diez pruebas frontend completan las regresiones. El ensayo adicional construye
BM25 exclusivamente sobre datos sintéticos, sin invocar FAISS ni descargar modelos.

El [informe de cobertura](T05-evidence/coverage.json), reproducible con
`python tools/check_ingestion_coverage.py`, comprueba conservación de las copias
heredadas en memoria. Resultado: conservación exacta en los 14 archivos (13 con
contenido y uno vacío), 775.545 bytes originales, 762.363 caracteres normalizados
y 872 fragmentos. La línea más larga tiene 1.609 caracteres. Todos los controles
de tamaño, solape, posiciones y hashes pasan. No las admite en un corpus de
análisis ni certifica que su contenido sea correcto.

T05 deja lista la mecánica de ingesta para revisar. El saneamiento material y
aprobación de documentos continúan pendientes de T04/T05. T06 debe vincular
manifiesto, corpus e índice realmente seleccionados; el runtime aún conserva
la compatibilidad con chunks heredados. T08, T10–T13 y la evaluación del despacho
siguen siendo necesarios. T03 mantiene el bloqueo de previews Vercel pendiente
de sus registros. No se ha fusionado, promovido producción ni usado un expediente
real. Esta evidencia acredita desarrollo y comprobaciones técnicas, no
transferencia efectiva al despacho ni un mérito ANECA por sí sola.
