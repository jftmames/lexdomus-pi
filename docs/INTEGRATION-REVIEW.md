# LexDomus — expediente consolidado de preparación de integración

Estado: borrador técnico para revisión. Uso real no habilitado. Alcance propuesto,
pendiente de confirmación: cesión y edición de obras literarias, derecho español,
uso interno del despacho. No hay aprobación jurídica registrada ni fusión de PR.

## Juicio técnico

La demo mecánica está preparada para sus dos ejemplos ficticios. El analizador
para contratos reales **no está terminado**. No basta cambiar una variable de
Vercel ni admitir documentos para ponerlo en servicio. Los bloqueos se enumeran
abajo y no se consideran resueltos por el número de tests.

## Trabajo completado en este bloque

- Extracción revisable de 40 artículos; corregidas 20 omisiones en 11 artículos.
- Comparación reproducible de coincidencia léxica, BM25 y fragmentación por
  párrafos completos, sin activar ninguna de las alternativas experimentales.
- Corrección del pipeline: generar exige candidatos en cada cuestión identificada.
  La evidencia parcial conserva citas pero produce `INSUFFICIENT_EVIDENCE`, sin
  opinión, alternativa ni EEE. El cliente y la API aceptan ese estado y rechazan
  un borrador con cuestiones sin candidatos.
- Eliminado el reintento que añadía la cláusula completa a una cuestión vacía:
  coincidencias de otro asunto podían simular evidencia. Se consulta únicamente
  la pregunta de cada nodo.
- La demo y el ensayo sintético usan ahora una pregunta explícita igual al token
  de prueba. Es una fixture declarada, no un sustituto de Inquiry real.

## Recuperación: resultado y alcance

| Configuración offline | Casos con cobertura completa / 16 |
| --- | ---: |
| Coincidencia léxica, ventanas de 1000 caracteres | 9 |
| BM25, mismas ventanas | 11 |
| BM25, párrafos completos agrupados hasta objetivo 1000 | 12 |

La comparación por párrafos mantiene las consultas, seis resultados y parámetros
BM25. Cambian las unidades indexadas y sus estadísticas: 60 fragmentos frente a
59. Máximo 996 caracteres; no hubo párrafos sobredimensionados en esta entrada.
La media de caracteres devueltos por consulta pasa de 4406,58 a 4049,33, contando
el texto de cada resultado, incluidos solapes en la referencia. Se gana N03 sin
regresiones de cobertura en esta muestra. Si un párrafo excede el objetivo, el
prototipo lo conserva completo y registra su tamaño; no es una política de
producción para documentos arbitrariamente grandes.

Persisten C02, C04 y N04 (paráfrasis) y C08 (falta un segundo pasaje necesario).
Las ocho pruebas de alcance devuelven candidatos en las tres configuraciones.
No se ejecutó una API jurídica sobre estos textos; devolver candidatos no es una
medida de respuestas erróneas. Las expectativas son provisionales y redactadas
por el implementador, no una validación independiente del despacho.

Evidencia: [comparación por párrafos](T04-evidence/boe-paragraph-comparison.json),
[comparación de rankers](T04-evidence/boe-ranker-comparison.md) y
[artículos para cotejo](T04-evidence/boe-articles-review.md).

## Bloqueos reales antes de abrir contratos

| Bloqueo | Hallazgo comprobado | Condición de cierre |
| --- | --- | --- |
| Procedencia y admisión | Capturas DOM; descarga HTTP de originales incompleta; política pendiente y 14 copias en cuarentena | Conservar originales, cotejar versión/extracción y registrar decisión jurídica sobre fuentes |
| Inquiry | `verdiktia/inquiry_engine.py` devuelve dos preguntas fijas con plantillas, independientemente del contrato | Implementar y evaluar identificación de cuestiones, alcance y contexto temporal con casos revisados |
| Recuperación | Quedan cuatro casos de referencia sin cobertura completa en el mejor ensayo | Resolver paráfrasis y soporte múltiple con evaluación ampliada y revisada; no ajustar un diccionario a los casos conocidos |
| Suficiencia | El control nuevo exige candidatos por nodo, pero aún no determina pertinencia ni soporte de la conclusión | T08: criterio de evidencia por cuestión y abstención verificable ante citas irrelevantes, incompletas o versiones inaplicables |
| Operación con textos reales | El despliegue es una demo de tokens; no demuestra controles de acceso, tratamiento de entradas, trazabilidad protegida ni readiness integral | Implementar y verificar estos controles para el uso interno acordado antes de aceptar contratos |
| Integración | Trabajo en rama de borrador; cron heredado de main no se detiene al editar esta rama | Revisar CI del commit final, dependencias de PR #7/#8, promoción/reversión y situación de workflows en main |

El modo activo continúa siendo `lexical-overlap-v1`. Ni BM25 ni la fragmentación
experimental sustituyen silenciosamente el formato de snapshot T06. Su eventual
integración exige versionar preparación/carga y repetir los controles de
integridad, además de medir recuperación.

## Decisiones concentradas para el responsable

1. Confirmar o restringir el alcance propuesto de cesión/edición ES y uso interno.
2. Designar al revisor jurídico. No se ha rellenado nombre, acta ni fecha de
   aprobación por anticipado.
3. Revisar la [ficha de casos](T04-evidence/legal-review-checklist.md): confirmar
   pasajes, remisiones, condiciones temporales, exclusiones y abstenciones.

La revisión no consiste en aprobar globalmente un portal o firmar los resultados
numéricos. Debe identificar material y versión admitidos y las expectativas que
se aceptan o corrigen. No se solicita aún autorizar producción ni fusionar PR.

## Verificación de esta entrega

124 tests Python del núcleo, 10 pruebas de herramientas de revisión y 12 pruebas
frontend pasan localmente. TypeScript y compilación de producción del frontend
también completan correctamente. Se comprueba reproducción del ensayo de párrafos,
contrato API, bloqueo de generación ante evidencia parcial y ausencia de rescate
por términos ajenos. Los ensayos del piloto usan exclusivamente datos ficticios.
La CI remota del nuevo commit debe revisarse por separado; estos números no
certifican extracción jurídica completa, relevancia ni seguridad operativa.

## Orden de ejecución posterior

Primero fijar las expectativas jurídicas y construir Inquiry con detección de
alcance. Después resolver recuperación y suficiencia sobre esas cuestiones, e
integrar el modo seleccionado con snapshots versionados. Completar los controles
operativos y ensayar el circuito entero antes de proponer la apertura real.
La adquisición documental puede avanzar en paralelo cuando esté disponible la
conexión de descarga. Este expediente concentra lo pendiente; evita promover
cada mejora local como si cerrara la puesta en servicio.
