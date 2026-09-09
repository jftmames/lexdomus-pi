# T04.1 — registro de fuentes y bloqueo técnico de política

Fecha: 9 de septiembre de 2026. Base: T03 `86e14b53145ca0ba0c4bbdd450a6e0e6b08f4194`.
Propuesta en borrador. **T04 permanece abierta: ninguna fuente ni política ha
sido aprobada por el despacho.**

## Problema y efecto del cambio

La ausencia de `policies/policy.yaml` hacía que el servicio admitiera por defecto
BOE, EUR-Lex, WIPO y USC. El fichero heredado `policy.yam` contiene sólo un salto
de línea. El inventario revela que una etiqueta BOE puede acompañar a un documento
distinto del esperado. La autoridad de un portal no basta para validar el texto.

La política nueva está versionada y contiene cero fuentes admitidas, revisión
pendiente y ningún revisor inventado. Se conserva el fichero `.yam` como vestigio;
no se carga. Su ausencia, YAML inválido, duplicados, campos desconocidos, estado
pendiente o aprobación incompleta impiden analizar. No existe política de respaldo.

El pipeline comprueba la política antes de descomponer la cláusula. RAG y el
recuperador directo también la exigen, incluso cuando no se pasa una política.
Una política explícita inválida genera `PolicyError`; nunca se sustituye por otra.
`POST /analyze` devuelve HTTP 503 con el contrato `0.2`, estado `TECHNICAL_ERROR`
y un identificador. El mensaje público no expone el YAML, rutas ni contenido del
expediente. La interfaz indica que el responsable debe revisar la configuración.

Para una política con revisión registrada, se filtran la etiqueta exacta de
fuente, la jurisdicción del documento y un hostname HTTPS exacto antes del límite
de resultados. No se admiten credenciales, puertos distintos de 443, subdominios
por coincidencia parcial ni etiquetas desconocidas. El piloto sólo permite
peticiones ES. La posible pertinencia de fuentes EU/INT dentro de ES debe
declararse por fuente y justificarse profesionalmente; las fuentes US se excluyen.

## Registro y revisión

[T04-sources.md](T04-sources.md) inventaría las 14 copias locales con hashes,
origen, versión declarada, defectos y condiciones publicadas por cada proveedor.
Los hashes identifican las copias examinadas; no prueban autenticidad ni vigencia.

La política exige identificador, revisión numérica, fecha de referencia y estado
de revisión. Una revisión aprobada requiere nombre de revisor, fecha no futura
igual o posterior a la fecha de referencia y referencia a su acta. **El código
valida que esos campos existan y sean coherentes; no autentica al revisor ni
verifica la firma o el contenido del acta.** Control de acceso y trazabilidad
corresponden a T10/T11. No hay aprobación implícita por escribir `approved`.

No se usa un límite de antigüedad del año normativo: una referencia de 1996 no
se descarta automáticamente. La selección de la versión y su aplicabilidad al
supuesto exige revisión jurídica; este cambio no la automatiza.

## Comprobaciones

```bash
USE_LLM=0 python -m unittest discover -s tests -p 'test*.py' -v
USE_LLM=0 python -m tests.smoke
npm --prefix web test
```

48 pruebas Python: las 39 anteriores más 9 sobre carga de política, YAML ambiguo,
fechas, aprobación pendiente, rechazo anticipado, scope, hosts y respuesta 503.
Las políticas aprobadas de los tests son ficticias, usan `example.invalid` y se
inyectan sólo sobre fixtures temporales. No se escriben en la política del servicio.

Los 10 casos heredados de `tests.smoke` sólo afirmaban flags e incluyen EU/INT,
fuera del piloto. Ahora ejercitan directamente ese detector: no se les concede
una excepción de política para recorrer el pipeline. Las regresiones de contratos
y API siguen probando el pipeline real con fixtures sintéticos y red bloqueada.
Las 9 pruebas frontend incluyen la respuesta 503 dentro del caso de errores HTTP.

## Cierre pendiente y decisión profesional

1. Corregir identidad, idioma, texto vacío y resúmenes locales; establecer las
   versiones canónicas y ligar cada chunk al documento comprobado (T05/T06).
2. Resolver pertinencia y reutilización de cada fuente. WIPO Lex tiene condiciones
   específicas; no se presupone permiso comercial o de scraping por la licencia
   general de WIPO. Cornell mezcla legislación y contenido editorial. Ambos están
   fuera de la política propuesta, que no admite ninguna fuente todavía.
3. El profesional debe documentar fuentes concretas, versión, fecha de referencia,
   alcance de revisión y criterios de evidencia/abstención (T04/T08). No basta con
   aprobar un hostname.
4. Vincular esa decisión a la política antes de habilitar un piloto y completar
   acceso, trazabilidad y validación técnica/jurídica de los restantes P0.

Los scripts de descarga/vigilancia heredados no consumen aún esta política.
No se han ejecutado ni cambiado en esta propuesta; su promoción segura está en
T13. Esta rama no detiene las ejecuciones programadas existentes en `main`.
Por tanto, el bloqueo aquí descrito afecta a la ruta activa de análisis, no
constituye una solución completa de gestión del corpus.

`/health` sigue indicando disponibilidad básica incluso con política pendiente;
readiness es T12. El filtro por hostname tampoco demuestra identidad documental,
contenido, procedencia de cada fragmento ni suficiencia de las citas. No deben
retirarse estos bloqueos sólo para obtener una demo o preparar el expediente ANECA.

## Estado de T03

Los jobs frontend, smoke y Docker del commit base terminaron correctamente en
[push](https://github.com/jftmames/lexdomus-pi/actions/runs/34399933152) y
[PR](https://github.com/jftmames/lexdomus-pi/actions/runs/34399953461).
Una prueba local del constructor publicado `@vercel/next@11.0.3` sobre copia
limpia del mismo commit completó instalación, compilación y empaquetado de
funciones: 34 salidas y 28 rutas, exit 0. No reproduce la plataforma ni ajustes
de los proyectos alojados; no determina la causa de sus fallos.

Las [dos previews fallidas de T03](https://github.com/jftmames/lexdomus-pi/pull/4)
siguen pendientes de registros de Vercel. T04.1 puede revisarse por separado,
pero no convierte T03 ni el piloto completo en tareas cerradas.
