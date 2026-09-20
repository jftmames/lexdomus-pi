# Piloto sintético en Vercel

La raíz del repositorio despliega exclusivamente `pilot.main:app` (FastAPI,
Python 3.12); `web` despliega Next.js en un proyecto distinto. Se sustituye la
configuración raíz heredada `@vercel/next@11.0.3`. No fusionar esta rama todavía.
Los proyectos existentes que usen la raíz recibirán este cambio sólo en las
previews de esta rama; `main` no se modifica.

La API admite exactamente `zafiroqwerty` y `inexistenteqwerty`, con jurisdicción
ES. El primero recupera un token de una fuente marcada SYNTHETIC y el segundo
se abstiene. No son cláusulas jurídicas ni una prueba de calidad semántica.

La fuente, el registro y la política ficticios se crean en un directorio temporal
único. El flujo normal de ingesta y verificación produce una versión inmutable en
memoria. Se elimina el directorio temporal. No se consultan ni se modifican la
política, el registro, la cuarentena o la selección de corpus reales. La API no
acepta rutas ni identificadores de corpus del cliente o del entorno.

El pipeline recibe explícitamente la política, snapshot y redactor sintéticos.
El redactor no llama a proveedores, incluso con USE_LLM=1. Se desactiva la traza
de cláusulas y no se muestran alternativas heurísticas ni puntuaciones EEE.
`/health` muestra el contexto de recuperación y `synthetic_only: true`.

Frontend: configurar NEXT_PUBLIC_SYNTHETIC_PILOT=1 y NEXT_PUBLIC_API_BASE con
la URL HTTPS de la API. Se ofrecen dos botones de ejemplo y el texto es de sólo
lectura. CORS admite únicamente https://lexdomus-pi-piloto.vercel.app.
No hacen falta claves de modelos ni una base de datos.

Verificación: `python -m unittest tests.test_pilot` y suite completa. Validar
además ambos botones en la página publicada. No considerar este despliegue como
aprobación del corpus real ni como solución al fallo conocido de sinónimos.

El runtime Vercel usa `.python-version` 3.12 y `uv.lock`. Los tres workflows
conservan explícitamente Python 3.11.16 y los locks T03 originales.
