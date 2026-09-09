# T03 — dependencias y entornos reproducibles

Fecha de comprobación: 9 de septiembre de 2026. Propuesta sobre T02
(`01fc9094c344f5161e5357fe87b740909d168b12`, PR #3), sin fusión a `main`
ni promoción de producción. No se habilitan expedientes reales.

## Resultado y decisiones técnicas

Se fijan las dependencias directas y transitivas de API/núcleo e interfaz,
se actualizan componentes con avisos conocidos y se elimina el `postinstall`
que sobrescribía archivos de la interfaz. No se cambia el algoritmo jurídico,
el corpus ni los índices. El alcance del piloto permanece sintético y ES.

| Componente | Versión propuesta | Motivo |
| --- | --- | --- |
| Python | 3.11.16 | Unificar Docker, CI y desarrollo; soporte de seguridad hasta octubre de 2027. |
| FastAPI / Starlette | 0.141.1 / 1.6.0 | Sustituir el entorno anterior con Starlette 0.36.3 y avisos de seguridad. |
| Pydantic / Uvicorn | 2.13.5 / 0.52.4 | Resolución compatible comprobada con el contrato existente. |
| Node / npm | 24.19.0 / 11.9.0 | Unificar el entorno de referencia y la instalación con `npm ci`. |
| Next.js / React | 16.3.4 / 19.2.8 | Pasar de Next 14 sin soporte a la rama 16 Active LTS. |
| TypeScript | 6.0.3 | Mantener la API de compilación usada por las pruebas actuales. |
| Tailwind / PostCSS | 3.4.19 / 8.5.28 | Preservar CSS y corregir dependencias sin migrar a Tailwind 4. |

El SDK OpenAI queda en 3.10.0; se revisaron sus interfaces usadas, sin llamadas
reales. NumPy 2.4.6 conserva compatibilidad con Python 3.11. Se retira
`framer-motion` porque no se encontraron importaciones. No se introducen
bibliotecas de pruebas en el producto.

Fuentes primarias consultadas: [Python 3.11.16](https://www.python.org/downloads/release/python-31116/),
[ciclo de Python](https://devguide.python.org/versions/),
[soporte Next.js](https://nextjs.org/support-policy),
[actualización de seguridad de agosto](https://nextjs.org/blog/august-2026-security-release)
y [Next.js 16.3.4](https://github.com/vercel/next.js/releases/tag/v16.3.4).

## Qué significa reproducible aquí

`requirements.in` y `requirements.api.in` expresan dependencias directas.
`requirements.api.txt` contiene 35 distribuciones, incluido el núcleo;
`requirements.txt` contiene las 25 del núcleo, con versiones compartidas
idénticas. Ambos bloquean versiones y hashes. El entorno de resolución es
CPython 3.11.16, Linux x86_64: no se afirma resolución universal por plataforma.
`web/package-lock.json` fija 137 entradas, incluidas alternativas opcionales;
no todas se instalan en cada máquina.

La instalación normal usa los locks existentes, sin actualizarlos:

```bash
python -m pip install --require-hashes -r requirements.api.txt
python -m pip check
npm --prefix web ci --no-audit --no-fund
```

La regeneración se hace en un entorno separado con `pip==26.2.1` y
`pip-tools==7.6.1`, nunca añadiendo estas herramientas al producto:

```bash
export CUSTOM_COMPILE_COMMAND='See docs/T03-dependencies.md for the reproducible lock commands'
python -m piptools compile --generate-hashes --resolver=backtracking --strip-extras --no-emit-index-url --no-emit-trusted-host --output-file=requirements.api.txt requirements.api.in
python -m piptools compile --generate-hashes --resolver=backtracking --strip-extras --no-emit-index-url --no-emit-trusted-host --constraint=requirements.api.txt --output-file=requirements.txt requirements.in
```

Conservar los locks y no usar `--upgrade` reprodujo ambos byte a byte. Una
actualización deliberada requiere revisar los `.in`, resolver primero API
con `--upgrade`, regenerar el núcleo restringido por ese lock y repetir las
pruebas y auditorías. Para npm, modificar las versiones exactas en
`web/package.json`, resolver con el Node/npm fijado y revisar el diff completo
del lock antes de repetir `npm ci` en limpio.

## Seguridad: alcance de la evidencia

Auditorías del 09/09/2026, conservadas en [T03-evidence](T03-evidence/):

- Python anterior: 9 registros, **7 avisos distintos**, en Starlette 0.36.3.
  Corresponde al entorno T02 realmente instalado, no a un lock histórico
  inexistente; contiene también paquetes residuales no utilizados.
- Python propuesto: `pip-audit==2.10.1` devuelve **0 hallazgos**, sin exclusiones
  ni paquetes omitidos, para las 35 distribuciones del lock API.
- Interfaz anterior: **38 GHSA distintos**, agrupados por npm en dos paquetes
  (Next.js y PostCSS). No todos son explotables en esta aplicación: algunos
  dependen de Windows o de funciones/configuraciones no utilizadas.
- Interfaz propuesta: `npm audit --json` devuelve **0 hallazgos conocidos**.

Estos resultados son una fotografía de las bases consultadas: no certifican
ausencia de vulnerabilidades ni cubren sistema operativo, aplicación, servicios
alojados o seguridad jurídica. No se ejecutó `npm audit fix --force`.

## Construcción, CI y despliegue

Se fijan las acciones de los siete workflows por SHA, los runners en
`ubuntu-24.04` y la versión de Python mediante `.python-version`. El workflow
de regresión se ejecuta en todo push/PR, sin filtros que omitan cambios de
configuración. Comprueba contratos, tipos, compilación, inventario y Docker.
Las acciones y runners siguen dependiendo de la disponibilidad de GitHub.

La imagen de API utiliza `python:3.11.16-slim-bookworm` con digest
`sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84`,
instalación de ruedas con hashes y usuario 10001. `.dockerignore` permite
sólo código de ejecución y artefactos demo seleccionados. No copia casos,
logs ni archivos de entorno. No se afirma que los artefactos demo sean válidos
jurídicamente.

El contenedor de desarrollo combina ese Python con
`node:24.19.0-bookworm@sha256:4196d66a565c6f195728d9952f161f4adfe2ad753052a08b7ec7f1c5a6bda42b`.
Se elimina el arranque obsoleto de Streamlit y se documentan los puertos
8000/3000 sin iniciar servicios automáticamente. Se retira el archivo inactivo
`tests/workflows/tests.yml`; la CI ejecutable reside en `.github/workflows/`.

Vercel conserva las rutas existentes y fija `@vercel/next@11.0.3` con
instalación `npm ci`. Las versiones de parche gestionadas por Vercel no quedan
inmovilizadas por esto. Las previews automáticas deben comprobarse al publicar
la PR, y no equivalen a validación del backend ni a promoción de producción.

El push de `Build RAG indices` se restringe a `main` para evitar commits
automáticos sobre ramas de revisión. **Pendiente:** los workflows de corpus
heredados aún contienen staging amplio y recuperación de conflictos que deben
revisarse en el bloque de mantenimiento. No se han ejecutado manualmente ni
se declara validado su efecto sobre fuentes externas.

## Verificación y reversión

Validado localmente: instalaciones limpias con hashes y `pip check` de API y
núcleo; 39 regresiones Python; 10/10 smoke; 9 pruebas de interfaz; TypeScript y
compilación; inventario coherente y sin escritura en `--check`; detección de
alteraciones de locks/licencias; SBOM válido contra el esquema oficial
CycloneDX 1.6 con `jsonschema==4.25.1` en entorno separado.

La exportación OpenAPI sólo elimina cuatro `enum` unitarios redundantes con
`const`; conserva las mismas restricciones y la versión contractual 0.2.
No se han usado proveedores reales ni datos de clientes.

Docker no está disponible en el entorno local: su construcción y prueba quedan
como condición pendiente de CI. La aceptación de T03 requiere CI y previews
correctas sobre el commit publicado; hasta entonces permanece en borrador.

Reversión de código: revertir únicamente el commit de T03 en la rama de
propuesta, preservando T02. No modificar `main` ni reescribir historia.
Un fallo de migración no justifica poner en producción las dependencias
anteriores con avisos conocidos. La reversión de un despliegue requiere además
identificar su artefacto y configuración; no se ha realizado ni ensayado una
reversión de producción.

## Inventario y transferencia

El [SBOM y las licencias](dependencies/README.md) contienen 172 entradas y
58 archivos declarados de licencias Python. Las declaraciones de paquete no
cubren por sí solas todo el código nativo incluido: véanse NumPy, lxml y uvloop.
Los textos completos de licencias npm no se recopilan en este inventario.

T03 documenta mantenimiento y verificaciones técnicas. Sigue siendo necesario
sanear corpus/política, validar resultados y seguridad, acordar el piloto con
el despacho y registrar su uso e impacto. No se afirma transferencia efectiva
ni mérito ANECA por completar una actualización de dependencias.
