# Adquisición y extracción de revisión del BOE

Estado: revisión pendiente; ninguna fuente admitida. Trabajo sobre la propuesta
`4f3a1eb`, sin modificación de política, registro ni servicio Vercel.

## Resultado y límite de procedencia

La ejecución del plan con `scripts/fetch_corpus.py` falló por resolución DNS de
`www.boe.es` (NameResolutionError). El descargador eliminó su directorio parcial;
no hay un manifiesto de descarga satisfactoria ni hashes de originales HTTP.

El navegador sí permitió consultar la redacción fechada y guardar los 40 bloques
DOM seleccionados y el texto mostrado del aviso legal. Los archivos incluyen la
fecha efectiva de captura proporcionada por el reloj del navegador. Son copias
del DOM/texto mostrado, no los bytes originales enviados por el BOE. Los hashes
calculados identifican estas capturas y su extracción, nunca un original HTTP.
La publicación de origen de 1996 no se ha conservado localmente.

## Archivos y reproducción

- `boe-dom-capture.json`: bloques HTML del DOM, identificadores y URL fechada.
- `boe-reuse-dom-capture.json`: texto mostrado del aviso y URL de procedencia;
  material de revisión, no fuente normativa para indexar.
- `boe-articles-review.json`: texto por artículo, hashes, enlaces y notas aparte.
- `boe-articles-review.md`: versión legible de la extracción.

Ejecutar desde la raíz, con las dependencias del proyecto:

```bash
python tools/extract_boe_review.py
```

La transformación selecciona títulos y párrafos directos de cada artículo,
normaliza espacios mediante el parser y separa las notas del BOE. Los selectores
de versiones históricas y la navegación quedan fuera del texto extraído; la
captura conserva su estructura para comparación. No hay reescritura mediante LLM.

## Comprobaciones realizadas

Se ha comprobado el conjunto exacto de 40 identificadores, unicidad, texto no
vacío, conservación del marcador de derogación del artículo 54, los cinco
apartados del artículo 43 y separación de las notas del artículo 48 bis.
La revisión posterior detectó 20 párrafos `parrafo_2` omitidos en 11 artículos.
Se han recuperado y regenerado ambos archivos de extracción. El extractor ahora
rechaza párrafos y elementos directos desconocidos en lugar de omitirlos. Tres
pruebas de regresión cubren las omisiones, notas, derogación y marcado inesperado. Estas
comprobaciones no equivalen al cotejo jurídico completo ni a evaluar recuperación.

El artículo 54 no debe tratarse como una disposición sustantiva vigente. Su
marcador se conserva para evitar que la extracción lo presente como un vacío.
La decisión de indexación deberá excluirlo de soporte positivo y conservar la
advertencia sobre derogación.

Las notas identifican modificaciones de 1998, 2003, 2006, 2007, 2014, 2018,
2019 y 2021. Sus enlaces exactos se conservan en `note_links`. Es preciso
contrastar las publicaciones relevantes antes de aprobar el alcance temporal;
conservar sólo la publicación inicial de 1996 no resuelve este requisito.

## Trabajo pendiente

1. Completar adquisición de originales y manifiesto en un entorno que pueda
   ejecutar el descargador; contrastar con estas capturas y conservar condiciones.
2. Cotejar artículos, notas, versiones, remisiones y alcance con el revisor;
   documentar atribución y presentación conforme a las condiciones del BOE.
3. Fijar expectativas por pasaje y evaluar los doce casos propuestos; corregir
   recuperación y suficiencia antes de plantear apertura a entradas reales.

Estos archivos permanecen en documentación y no son un candidato T05, un snapshot
T06 ni un registro aprobado. Las 14 copias antiguas siguen en cuarentena.

## Diagnóstico posterior

La [evaluación reproducible](boe-retrieval-diagnostic.md) usa la extracción
corregida. La comprobación previa de 40 identificadores no acreditaba integridad
del texto; no debe citarse como si lo hiciera. La descarga directa se volvió a
intentar y sigue sin completarse.
