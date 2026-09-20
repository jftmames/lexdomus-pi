# Diagnóstico de recuperación sobre la extracción BOE

Estado: ensayo offline, expectativas provisionales, fuentes no admitidas.
No se ha ejecutado `/analyze`, ni aprobado una política, ni creado un snapshot
real. No hay generación ni consultas a modelos. El piloto Vercel no cambia.

## Resultado

Se recuperaron íntegramente los pasajes de referencia en **4 de 8 casos**. Los
cuatro casos adicionales de alcance/abstención devolvieron candidatos, pero no
se puntúan como respuestas jurídicas: aquí no se ejecuta la compuerta de evidencia.
No se presenta este resultado como precisión del producto ni validación del despacho.

| Caso | Consulta abreviada | Cobertura completa de pasajes provisionales |
| --- | --- | --- |
| C01 | Cesión sin tiempo ni territorio | Sí, art. 43 |
| C02 | Hasta cuándo y en qué países | No, falta art. 43 |
| C03 | Medios de difusión que se inventen | No, falta pasaje del art. 43 |
| C04 | Acuerdo verbal | No, falta art. 45 |
| C05 | Cesión con carácter exclusivo | Sí, art. 48 |
| C06 | Solo esta editorial podrá explotar | Sí, art. 48 |
| C07 | Renuncia a que figure el nombre | Sí, pasajes propuestos del art. 14 |
| C08 | Omisión del número de ejemplares | Parcial: art. 60, falta art. 61 |
| C09 | Cesión y patente estadounidense | Devuelve candidatos; exige delimitar cuestiones |
| C10 | Tratamiento fiscal del pago | Devuelve candidatos con una sola palabra compartida |
| C11 | Aplicar redacción a contrato de 1997 | Devuelve candidatos; no verifica fecha aplicable |
| C12 | La obra del puente | Devuelve candidatos; no distingue sentido de «obra» |

## Método reproducible y límites

```bash
python -m unittest tools.test_boe_review_extraction -v
python tools/evaluate_boe_review.py --check
```

Entrada: `boe-articles-review.json` corregido; su hash figura en
`boe-retrieval-review.json`. Son 40 artículos; se excluye el 54, que contiene un
marcador de derogación, del soporte positivo. Los 39 restantes producen 59
ventanas usando `split_text` del proyecto (1000 caracteres, solape 120).

Se usa `tokenize` de T06 y se replica su puntuación por intersección de tokens,
con desempate estable y seis resultados, el límite de `rag_pipeline`. Las
ventanas se forman por artículo independiente, en orden DOM. Este orden y unidad
pueden diferir de la futura ingesta; no se afirma paridad con un snapshot real.
No se omite ni se falsifica la aprobación para llamar al pipeline: el diagnóstico
se ejecuta como análisis de texto separado de la ruta autorizada.

Las referencias se fijaron antes de puntuar como párrafos completos. Se comprueba
su cobertura por la unión de ventanas recuperadas, no sólo la aparición del
número de artículo. C08 requiere dos pasajes de artículos distintos. C07 incluye
el encabezamiento sustantivo y los apartados 2.º y 3.º. Todas estas expectativas
requieren revisión profesional y no agotan el soporte jurídico necesario.

## Corrección previa de extracción

La primera extracción omitía los párrafos con clase HTML `parrafo_2`: 20 párrafos
en 11 artículos. La cobertura por identificadores no detectaba esa pérdida.
Se corrigió el extractor, se regeneraron texto y hashes y se añadieron regresiones
para disposiciones omitidas y marcado desconocido. El DOM conservado no se alteró.
La regla nueva falla ante elementos directos no clasificados, para evitar nuevas
omisiones silenciosas. Esto no sustituye el cotejo completo con los originales.

## Siguiente cambio recomendado

Preparar un comparador offline de ranking léxico con ponderación de términos
(BM25 o equivalente) y un conjunto de paráfrasis independiente. Medir cobertura
por pasaje y falsos positivos frente a este resultado, sin cambiar aún el modo
activo `lexical-overlap-v1`. No basta añadir un diccionario ajustado a C02 ni
subir k hasta que entren todos los artículos.

En paralelo, T08 debe definir soporte por cuestión y condiciones de abstención:
C08 muestra que una cita pertinente puede dejar incompleta la evidencia; C10–C12
muestran que el ranking por sí solo no certifica pertinencia o aplicabilidad.
La decisión de promover otro recuperador debe esperar resultados reproducibles
y criterios revisados, además de completar procedencia y admisión de fuentes.

La descarga directa de originales se volvió a intentar sin éxito. Las capturas
siguen identificadas como DOM, con hash propio y sin hash HTTP inventado.
