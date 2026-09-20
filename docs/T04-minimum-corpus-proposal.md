# Propuesta de corpus mínimo para el piloto editorial ES

Fecha de consulta: 20 de septiembre de 2026. Estado: propuesta para revisión,
no aprobación ni activación. Base técnica: `72b0de1`, PR #8 en borrador.

## Decisión propuesta

Empezar con un único instrumento: el texto refundido de la Ley de Propiedad
Intelectual española, para ensayar cláusulas de cesión y edición de obras
literarias. Es un alcance de evaluación limitado, no una declaración de que
esta norma baste para resolver cualquier contrato. Los supuestos que necesiten
otras fuentes deben quedar sin conclusión hasta ampliar y revisar el corpus.

Las 14 copias heredadas siguen en cuarentena. La nueva adquisición tendrá su
propia procedencia; no se corregirá una etiqueta para dar por verificado un
archivo antiguo. EU, Berna y US quedan fuera de esta primera propuesta.

## Identidad y versión consultadas

La referencia correcta es **BOE-A-1996-8930**, Real Decreto Legislativo 1/1996,
de 12 de abril. La página consultada muestra como última actualización publicada
el **30/03/2022**. Esto no certifica por sí solo la aplicabilidad a un contrato.
El BOE advierte que la consolidación es informativa y que para fines jurídicos
hay que consultar las publicaciones oficiales.

- [Redacción fechada candidata](https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930&p=20220330&tn=1).
- [Publicación de origen](https://www.boe.es/buscar/doc.php?id=BOE-A-1996-8930).
- [Condiciones de reutilización](https://www.boe.es/informacion/aviso_legal/index.php).

La fecha de consulta, la actualización del texto y la fecha del supuesto son
campos distintos. Antes de admitirlo, el revisor deberá contrastar las
modificaciones relevantes y sus efectos temporales con sus publicaciones.

Bloques propuestos para evaluación, con artículos completos y sus remisiones:

| Materia | Artículos candidatos |
| --- | --- |
| Derechos morales y explotación | 14, 17–23 |
| Transmisión de derechos | 43–57, incluido 48 bis |
| Contrato de edición | 58–73 |

La selección es provisional. No se cortarán párrafos para fabricar respuestas
esperadas. Si una remisión requiere un artículo adicional, se revisará y ampliará
el alcance antes de utilizarlo como evidencia.

## Adquisición y revisión reproducibles

El [plan JSON](T04-evidence/minimum-corpus-download-plan.json) es compatible con
`scripts/fetch_corpus.py`. Descarga tres materiales para revisión: consolidación,
publicación de origen y aviso de reutilización. Los dos últimos sirven de
expediente de comprobación; no deben indexarse automáticamente como artículos
aplicables. El plan no incluye todavía todas las publicaciones modificadoras.

No se ha ejecutado la descarga ni hay hashes nuevos en esta propuesta. El paso
técnico siguiente es ejecutarla en un directorio absoluto nuevo fuera del
repositorio, conservar originales y manifiesto, y preparar una extracción
revisable. Un HTTP 200 no acredita identidad ni integridad jurídica.

| Comprobación pendiente | Evidencia que debe quedar registrada | Responsable |
| --- | --- | --- |
| Identidad y versión | Identificador, título, idioma, URL fechada, fecha de adquisición y SHA-256 del original | Implementación y revisor |
| Extracción | Texto por artículo, posiciones, comparación con original, exclusión de navegación y separación de notas | Implementación |
| Aplicabilidad | Fecha del supuesto, modificaciones y remisiones relevantes, alcance y exclusiones | Revisor jurídico por designar |
| Reutilización | Copia de condiciones consultadas y decisión documentada sobre el material concreto | Responsable por designar |
| Admisión | Acta, revisor, fecha, versión y hashes aceptados; actualización separada de política y registro | Revisor e implementación |

Las condiciones del BOE contemplan reutilización comercial y no comercial para
los documentos sujetos a ellas, con excepciones. Exigen atribución, enlace,
conservación de metadatos, identificación de cambios y fecha de actualización;
la consolidación debe identificarse como informativa. No debe sugerirse respaldo
del BOE ni alterarse el sentido. La extracción y la presentación de citas deben
incorporar estas obligaciones antes de activarse. La conclusión sobre el material
concreto sigue pendiente de revisión del aviso enlazado.

## Casos propuestos para aceptar la recuperación

Son entradas ficticias y expectativas provisionales, **no resultados ejecutados
ni un conjunto jurídicamente aprobado**. El revisor deberá fijar los pasajes
exactos suficientes y las abstenciones antes de medir. Encontrar cualquier
fragmento o acertar el nombre de la ley no cuenta como acierto.

| ID | Entrada ficticia | Evidencia candidata o conducta esperada |
| --- | --- | --- |
| C01 | La cesión no indica tiempo ni ámbito territorial. | Art. 43, pasaje sobre omisiones |
| C02 | No acordamos hasta cuándo ni en qué países podrá usarse la obra. | Mismo pasaje que C01; paráfrasis |
| C03 | Se ceden también todos los medios de difusión que se inventen. | Art. 43, pasaje específico |
| C04 | Cedemos los derechos mediante un acuerdo verbal. | Art. 45 |
| C05 | La cesión se concede con carácter exclusivo. | Art. 48; revisar remisiones |
| C06 | Solo esta editorial podrá explotar la obra. | Evidencia equivalente a C05; paráfrasis |
| C07 | El autor renuncia a que figure su nombre. | Art. 14, pasaje pertinente |
| C08 | El contrato de edición omite el número de ejemplares. | Arts. 60–61; cobertura conjunta |
| C09 | Valora la cesión y además una patente estadounidense. | Sin conclusión global; parte fuera de alcance |
| C10 | ¿Qué tratamiento fiscal tiene este pago? | Abstención por falta de fuente pertinente |
| C11 | Aplica esta redacción a un contrato de 1997. | No asumir correspondencia temporal; pedir revisión de versión |
| C12 | Texto ajeno al supuesto con palabras comunes: la obra del puente. | No aceptar coincidencias léxicas como soporte jurídico |

Criterios propuestos: medir recuperación por pasaje y por cada cuestión, con el
mismo límite de resultados de producción; comparar pares literales/paráfrasis;
registrar falsos positivos y abstenciones, no sólo una media de aciertos. Todos
los casos críticos aprobados deben pasar antes de abrir el alcance que ejercitan.
La muestra sirve de arranque y no constituye validación profesional completa.

## Orden de integración y bloqueos

1. Adquirir originales nuevos con el plan, preparar extracción y revisión de
   identidad, versión y reutilización. Incorporar las publicaciones modificadoras
   necesarias al expediente antes de aprobar la versión.
2. Obtener revisión documentada de fuentes y expectativas. Preparar ingesta y
   snapshot aislados con esa política de revisión; fijar sus identificadores.
3. Corregir y evaluar recuperación: T06 documenta el fallo de sinónimos. T08 debe
   exigir soporte suficiente por cuestión; una cita en una parte no permite
   concluir sobre las partes sin evidencia.
4. Completar los controles de acceso, tratamiento de entradas, trazabilidad y
   readiness necesarios para el alcance real, y ensayar el circuito completo en
   un entorno de revisión. No basta con que `/health` responda.
5. Revisar las PR y la promoción manual de workflows T13. Sólo después decidir
   integración, configuración real de Vercel y apertura del campo de entrada.

La documentación y el plan no alteran el servicio desplegado: `pilot/main.py`
acepta dos ejemplos fijos y genera un corpus ficticio. Habilitar textos reales
requiere otra implementación revisada; cambiar una variable o rellenar la política
no transforma este piloto en un servicio jurídico operativo.

Puede esperar la ampliación a otros portales, los índices vectoriales y el
embellecimiento de la interfaz. Bloquean el uso real la evidencia admitida, la
recuperación y suficiencia verificadas y los controles operativos de ese uso.

## Estado de esta entrega

- Política activa: pendiente; ninguna fuente admitida por esta propuesta.
- Registro activo: sin cambios; 14 copias en cuarentena.
- Revisor, acta y fecha de aprobación: pendientes, sin valores inventados.
- PR #7 y #8: no fusionadas por esta entrega.
- Verificación: formato y aceptación del plan por el validador existente;
  no se declaran pruebas de recuperación real ni descargas ejecutadas.
