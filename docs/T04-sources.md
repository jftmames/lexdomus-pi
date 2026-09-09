# T04 — Inventario y revisión pendiente de fuentes

Fecha de inspección local y consulta web: **9 de septiembre de 2026**. Base inspeccionada: commit `86e14b53145ca0ba0c4bbdd450a6e0e6b08f4194` (T03). Estado: **propuesta técnica; ninguna fuente aprobada para el despacho**. El piloto previsto es español y con casos sintéticos; los materiales estadounidenses quedan fuera de su alcance.

Este inventario describe copias existentes, identificaciones y condiciones publicadas. No certifica vigencia, integridad respecto de una edición oficial, suficiencia jurídica ni autorización de un uso concreto. Durante su elaboración no se han activado ni modificado los scripts heredados de descarga, vigilancia o ingestión; tampoco se han descargado copias al corpus ni reconstruido índices.

## 1. Artefactos observados

Hay **14 TXT, 775.545 bytes y 870 chunks almacenados**. Los resúmenes locales no tienen procedencia literal, autoría o fecha normativa acreditadas. Su atribución por nombre de archivo no los convierte en textos oficiales. Los hashes identifican exclusivamente los bytes locales inspeccionados.

| Archivo en `data/corpus/` | Bytes | Chunks | Tipo y hallazgo factual |
|---|---:|---:|---|
| `berne.txt` | 4.396 | 5 | Navegación OMPI y título del tratado; sin articulado. |
| `berne_excerpt.txt` | 260 | 1 | Resumen español de 6bis; sin versión ni procedencia literal acreditadas. |
| `berne_full.txt` | 104.606 | 119 | Cuerpo inglés y navegación española; cabecera de tratado enmendado en 1979. |
| `es_lpi.txt` | 3.721 | 5 | **Identidad errónea:** BOE-A-1996-8932, nombramiento judicial en Corcubión. |
| `es_lpi_excerpt.txt` | 557 | 1 | Resúmenes de arts. 14, 17 y 43; sin versión identificada. |
| `es_lpi_full.txt` | 469.794 | 536 | BOE-A-1996-8930 consolidado, actualización declarada 30/03/2022; mezcla articulado, notas e interfaz. |
| `eu_infosoc.txt` | 70.659 | 77 | Cuerpo español del acto original de 2001; interfaz/título incluyen EN; enlaza a consolidación de 2019. |
| `eu_infosoc_excerpt.txt` | 224 | 1 | Resumen genérico, sin articulado literal ni versión identificada. |
| `eu_infosoc_full.txt` | **0** | **0** | **Vacío.** |
| `us_usc_17.txt` | 61.709 | 63 | Agregación de §§106, 201 y 302, navegación y notas; fuera del piloto ES. |
| `us_usc_17_106.txt` | 21.003 | 23 | §106 en inglés, con notas; fuera del piloto ES. |
| `us_usc_17_201.txt` | 16.597 | 16 | §201 en inglés, con notas; fuera del piloto ES. |
| `us_usc_17_302.txt` | 21.661 | 22 | §302 en inglés, con notas; fuera del piloto ES. |
| `us_usc_17_excerpt.txt` | 358 | 1 | Resúmenes españoles sin traducción acreditada; fuera del piloto ES. |

| Archivo | SHA-256 de la copia local |
|---|---|
| `berne.txt` | `a69c0da053ebb83b888e3deb15a30b38e0579963f82a407f462b4b944b57c90c` |
| `berne_excerpt.txt` | `b4269b6595cf0902419cebd659264a33bee61ec31cc62c89cbd9045be8ef7871` |
| `berne_full.txt` | `6b911e66772a5042464d100f70e7006384e988ccf43a6cd956ce7cb61e4a1912` |
| `es_lpi.txt` | `546dc7ce2ff11636560508294db6c40a590a3af0461bb301f8304314f62e4316` |
| `es_lpi_excerpt.txt` | `e144dcf6341b84c19e4dea8300bb48858e0149a017edae26d41056331852d67a` |
| `es_lpi_full.txt` | `c0be7bddda3bb8cbcf9ef2fcdb73fd1c4bfa86a90aa5110f86e24dff71a28540` |
| `eu_infosoc.txt` | `5a7488fe9fc184a04cc5fa69157559e62b3406599370daf8870746a9a3ec08b9` |
| `eu_infosoc_excerpt.txt` | `df7de737a4fbb5bd8ba5b3a82fecd5afe53b41852e6f09bd6051e0737e8193fa` |
| `eu_infosoc_full.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `us_usc_17.txt` | `0eea13982a7444ce882f21c3eeda8e49a298a67e2db17601b0cf507cfe398509` |
| `us_usc_17_106.txt` | `c928d3a876e12456c87cabbb622caddfe97419f3c0d8cdba698071208196ebec` |
| `us_usc_17_201.txt` | `cefdd9acfca381d1dc5956635ba8ae6e9b3892d4cd041c8ad1fadea167ca670f` |
| `us_usc_17_302.txt` | `78d2fcc97d44fdc9918bcdddd248402b25253ed283f11f956766b56437ba64a2` |
| `us_usc_17_excerpt.txt` | `99c235f15c1bb5c0548506d0d15fdd11a608d42db147c5fb72156f6d97ec26df` |

## 2. Identidad, autoridad y versión

Las siguientes son las seis URLs exactas compartidas por `scripts/fetch_corpus.py` y `scripts/check_reforms.py`. La consulta acredita qué identifica cada página; no acredita que la copia local sea su reproducción íntegra y actual.

| Copia programada | URL configurada y autoridad publicadora | Identificación comprobada |
|---|---|---|
| `es_lpi_full.txt` | [BOE](https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930) | RDL 1/1996, de 12/04/1996; BOE de 22/04/1996; entrada en vigor 23/04/1996. La página muestra actualización consolidada de 30/03/2022. |
| `eu_infosoc_full.txt` | [EUR-Lex](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX%3A32001L0029) | Directiva 2001/29/CE, de 22/05/2001; DO L167 de 22/06/2001. Es el acto original; remite a consolidación de 06/06/2019. |
| `berne_full.txt` | [OMPI/WIPO Lex](https://www.wipo.int/wipolex/es/text/283698) | Texto **inglés auténtico** de Berna, revisión París 24/07/1971 y enmienda 28/09/1979. La ruta `/es/` no garantiza idioma español del tratado. |
| `us_usc_17_106.txt` | [Cornell/LII §106](https://www.law.cornell.edu/uscode/text/17/106) | Derechos exclusivos; texto federal reproducido por Cornell y notas. |
| `us_usc_17_201.txt` | [Cornell/LII §201](https://www.law.cornell.edu/uscode/text/17/201) | Titularidad; texto federal reproducido por Cornell y notas. |
| `us_usc_17_302.txt` | [Cornell/LII §302](https://www.law.cornell.edu/uscode/text/17/302) | Duración; texto federal reproducido por Cornell y notas. |

Cornell no es el órgano oficial editor del U.S. Code. Su [página de actualización](https://www.law.cornell.edu/uscode/about/how-current) declara actualmente cobertura hasta Pub. L.119-102, publicada por OLRC el **23/07/2026**. Ese dato no fecha nuestras copias locales.

El [BOE-A-1996-8932](https://www.boe.es/diario_boe/txt.php?id=BOE-A-1996-8932) confirma la identidad ajena a LPI del fichero `es_lpi.txt`. Debe quedar excluido como evidencia de propiedad intelectual.

Se identificaron dos alternativas documentales, **sin incorporarlas al corpus ni aprobarlas**:

- [InfoSoc consolidada española de 06/06/2019](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:02001L0029-20190606): muestra `02001L0029 — ES — 06.06.2019 — 002.001` y modificaciones de las Directivas 2017/1564 y 2019/790. Su aviso la identifica como instrumento documental sin efecto jurídico.
- [Berna, traducción oficial española](https://www.wipo.int/wipolex/es/text/283700), enlazada desde la [ficha de idiomas OMPI](https://www.wipo.int/wipolex/es/treaties/textdetails/12214). Queda pendiente comprobar el uso permitido y la vía de adquisición; encontrar su URL no autoriza automatizarla.

## 3. Condiciones publicadas: revisión profesional pendiente

**BOE.** El [aviso legal](https://www.boe.es/informacion/aviso_legal/index.php) recoge la licencia tipo de 27/06/2024, efectiva desde 28/06/2024. Permite reutilización comercial y no comercial de documentos incluidos, con atribución y enlace, fecha de actualización, identificación de modificaciones y conservación de metadatos. Exige identificar cada consolidado reutilizado como informativo y no sugerir oficialidad ni respaldo institucional. Hay exclusiones para diseño, marcas y derechos de terceros; la Biblioteca Jurídica Digital tiene régimen diferente. Debe verificarse qué elementos de la extracción quedan comprendidos.

**EUR-Lex.** El [aviso legal](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html) permite reutilización comercial/no comercial de documentos jurídicos salvo condiciones particulares. Consolidaciones, resúmenes y contenido editorial propiedad de la UE se ofrecen bajo CC BY4.0, con fuente e identificación de cambios; metadatos bajo CC0. Hay reservas relativas a terceros, signos y logos. La licencia no convierte un consolidado en publicación auténtica.

**WIPO Lex: restricción específica relevante.** Los [términos del servicio](https://www.wipo.int/en/web/wipolex/terms-of-use), §2.1.1, permiten reproducir textos jurídicos y traducciones para fines académicos, investigación y no comerciales con fuente original y WIPO Lex. El §2.2 prohíbe consultas automatizadas, adquisición/descarga/almacenamiento masivos y web scraping; el §2.3 requiere permiso para vender o sublicenciar datos. **No debe asignarse automáticamente la licencia general CC BY4.0 de WIPO a WIPO Lex.** La [política general](https://www.wipo.int/en/web/terms-of-use) se subordina a condiciones específicas. Antes de cualquier futura recarga o uso comercial se necesita revisar permisos y, en su caso, una fuente o canal alternativo. No se declara aquí autorizado ese uso.

**Cornell/LII.** Las [condiciones LII](https://www.law.cornell.edu/lii/terms/documentation) distinguen el texto gubernamental, sobre el que no afirman copyright, de la compilación, navegación, marcado y valor añadido propio. Estos últimos se ofrecen bajo CC BY-NC-SA2.5; publicar las páginas no implica consentimiento para redistribución comercial. Las copias locales mezclan texto legal, notas e interfaz: no procede etiquetar el fichero completo como dominio público. Su exclusión del piloto ES no resuelve por sí sola la revisión de la distribución del repositorio.

Estas son descripciones de condiciones consultadas, no un dictamen sobre su aplicación al proyecto. No se ha obtenido permiso adicional ni contactado con titulares.

## 4. Defectos técnicos comprobados en la base heredada

- **Descarga:** `fetch_one` sobrescribe tras respuesta HTTP satisfactoria sin validar identidad, idioma, fecha, articulado ni resultado vacío. Captura excepciones y solo imprime `WARN`. La limpieza conserva texto de interfaz, notas e índices; no conserva respuesta original ni trazabilidad completa de transformación.
- **Extractos:** `ensure_excerpt` no los actualiza cuando ya existen. Pueden permanecer junto a versiones completas diferentes; la selección por expresiones regulares no acredita una unidad jurídica íntegra.
- **Vigilancia:** se comparan seis copias locales con baseline; los ocho TXT restantes no están en la lista. Si falta baseline se inicializa con la copia actual sin marcar cambio. Un fichero vacío existente figura disponible. Comparar hashes no demuestra vigencia normativa ni éxito de descarga.
- **Identificación:** `ingest.detect_meta` asigna familia y autoridad por nombre. Esto convierte el documento judicial `es_lpi.txt` en supuesta LPI.
- **Citas:** `pinpoint = bool(ref_label)` trata etiquetas generales como pinpoints. Los cinco chunks de navegación/título de `berne.txt` tienen `pinpoint=true`. Los enlaces LPI son generales y su detección no distingue adecuadamente artículos `bis`/`ter`.
- **Fragmentación:** `group_lines` puede omitir una línea mayor que `max_chars` cuando no cabe como primera línea. Su avance `max(end-overlap_lines, end)` equivale a `end`, sin el solapamiento anunciado. No se ha ejecutado ingestión para este inventario.
- **Metadatos existentes:** de 870 chunks, 657 tienen URL y `pinpoint=true`; 213 carecen de URL, todos BOE: tres del documento erróneo y 210 de LPI completa. Las etiquetas efectivas son `WIPO/OMPI` y `USC (Cornell/LII)`, que deben contrastarse con los valores exactos de la política.

## 5. Criterio de cierre pendiente

Cada fuente candidata necesita identidad, versión y lengua verificadas; texto normativo separado de resúmenes/interfaz/notas; procedencia y transformaciones registradas; condiciones de adquisición y reutilización revisadas; y decisión documentada del responsable jurídico sobre pertinencia para el piloto. Ningún hash, resultado de pruebas o anotación de este inventario sustituye esa decisión. Los casos reales y la evidencia de transferencia profesional siguen pendientes de validación y uso efectivo por el despacho.
