# Comparación offline: coincidencia léxica y BM25

**Decisión técnica: mantener el recuperador activo y no promover BM25 todavía.**
La mejora observada es limitada y persisten fallos de cobertura y alcance.
Fuentes y expectativas pendientes de revisión; no habilita entradas reales.

## Resultados medidos

| Grupo | Casos con pasajes esperados | Coincidencia léxica | BM25 |
| --- | ---: | ---: | ---: |
| Ocho casos iniciales | 8 | 4 completos | 5 completos |
| Ocho consultas nuevas | 8 | 5 completos | 6 completos |
| Total descriptivo | 16 | 9 completos | 11 completos |

BM25 mejora C03 (medios futuros) y N06 (compra del manuscrito), sin regresiones
respecto a la cobertura binaria observada en esta muestra. Siguen fallando C02,
C04, C08, N03 y N04. Esto no acredita ausencia de regresiones fuera de la muestra,
ni mejora de la precisión: faltan juicios de relevancia para todos los candidatos.

Se añadieron ocho pruebas de alcance/abstención en total, cuatro existentes y
cuatro nuevas. Ambos métodos devuelven candidatos en las ocho. No se ejecutó la
API ni su compuerta; no se presenta esto como ocho respuestas jurídicas erróneas.

## Diseño y reproducción

Se congelaron las nuevas consultas y referencias antes de ejecutar la comparación.
Son probes redactadas por el mismo implementador, no un conjunto independiente o
validación ciega del despacho. No se ajustaron parámetros tras observar resultados.

Misma entrada, 59 ventanas de los mismos 39 artículos, seis resultados y mismo
desempate por orden de entrada. Se excluye el marcador de derogación del art. 54.
Tokens Unicode en minúsculas; sin eliminar palabras frecuentes, lematizar, expandir
sinónimos o ponderar repeticiones de la consulta. Los documentos sí conservan la
frecuencia de los términos para BM25.

BM25 experimental: `k1=1.2`, `b=0.75`, IDF positiva
`ln(1+(N-df+0.5)/(df+0.5))` y factor de frecuencia
`f*(k1+1)/(f+k1*(1-b+b*dl/avgdl))`. Los parámetros e IDF se documentan en
[Apache Lucene](https://lucene.apache.org/core/9_12_1/core/org/apache/lucene/search/similarities/BM25Similarity.html).
Es una implementación explícita para este ensayo, no una ejecución de Lucene ni
una afirmación de equivalencia exacta con sus puntuaciones. No añade dependencias.

El umbral `score > 0` sólo descarta ausencia de coincidencias. No certifica
relevancia y no convierte BM25 en detector de materia o de vigencia temporal.

```bash
python -m unittest tools.test_boe_review_extraction tools.test_boe_rankers -v
python tools/compare_boe_rankers.py --check
```

El JSON adjunto conserva consultas, referencias por posición, resultados,
puntuaciones, configuración y hashes de entrada y casos. La referencia léxica
se contrasta con el diagnóstico previo, incluido el orden de candidatos. La CI
comprueba reproducción, no exige que los fallos conocidos desaparezcan para
presentar una falsa validación jurídica. Pasan siete pruebas locales: tres de
extracción y cuatro de aritmética, entradas vacías, empates y cobertura sin huecos.

## Fallos que requieren cambios distintos

- **C02 y C04:** BM25 no recupera los pasajes propuestos ante estas paráfrasis.
  Ponderar términos no establece equivalencias conceptuales.
- **C08:** aparece el artículo 60 pero falta el 61; una referencia recuperada no
  satisface un caso con dos pasajes necesarios.
- **N03:** el art. 64 llega primero, pero la ventana acaba en el carácter 1000 y
  el párrafo esperado termina en 1019. Faltan 19 caracteres de ese párrafo. El
  fallo es de cobertura íntegra según el criterio fijado, no de ausencia total
  de un texto pertinente. No se suaviza el criterio después de medir.
- **N04:** la paráfrasis sobre ventas y pago no recupera el pasaje requerido.
- **Alcance:** materia, jurisdicción y fecha necesitan controles adicionales;
  el ranking por palabras no decide si puede emitirse una conclusión.

## Siguiente cambio concreto

Comparar offline una fragmentación que respete párrafos normativos completos,
manteniendo BM25, las consultas y el límite de seis resultados. El objetivo
inmediato es corregir pérdidas como N03 sin ocultar las demás: registrar también
el aumento de caracteres recuperados, los párrafos que excedan el límite y las
regresiones. No aumentar k ni cambiar las referencias para forzar aciertos.

La suficiencia por cuestión y las abstenciones siguen siendo un trabajo separado
(T08). La descarga de originales, la admisión del corpus y la revisión profesional
continúan pendientes. No se modifican política, registro, snapshots ni aplicación.
