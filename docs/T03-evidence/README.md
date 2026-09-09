# Evidencia T03 — 9 de septiembre de 2026

JSON de auditorías conservados sin modificar. Los ficheros `before` reflejan
el entorno anterior; `after`, las dependencias propuestas. No son una garantía
de ausencia de vulnerabilidades. `frontend-advisories.md` desglosa los avisos
anteriores; su presencia en una dependencia no demuestra explotabilidad aquí.

`python-lock-reproducibility.json` registra la regeneración idéntica de ambos
locks. `inventory-validation.json` registra comprobaciones de coherencia y
detección de alteraciones; los logs de diagnóstico permanecen fuera del producto.

Comprobación adicional al retomar T03: 39/39 regresiones Python, 10/10 smoke,
9/9 pruebas de interfaz, TypeScript y build correctos; OpenAPI coincide con su
exportación; siete workflows parsean como YAML y las configuraciones como JSON.
El SBOM supera el esquema oficial CycloneDX 1.6, validado con
`jsonschema==4.25.1` usando copias locales de `bom-1.6.schema.json`,
`spdx.schema.json` y `jsf-0.82.schema.json` del repositorio oficial
[CycloneDX/specification](https://github.com/CycloneDX/specification/tree/master/schema).

No se han ejecutado proveedores reales, expedientes de clientes ni despliegues
de producción. Véase el alcance
y los límites en [T03-dependencies.md](../T03-dependencies.md).

Actualización posterior a publicar T03: frontend, smoke e imágenes Docker
correctos en [CI push](https://github.com/jftmames/lexdomus-pi/actions/runs/34399933152)
y [CI PR](https://github.com/jftmames/lexdomus-pi/actions/runs/34399953461), ambas
sobre `86e14b53145ca0ba0c4bbdd450a6e0e6b08f4194`.

El [log del builder Vercel local](vercel-local-build.log) conserva una prueba
adicional sobre copia limpia del mismo commit: instalación, Next build,
trazado y funciones correctos; 34 salidas y 28 rutas, exit 0. SHA-256 del log:
`94b28606b103cd09b14a63ca0a400812dbfbd95a1ae87a2dcfd051d08a397789`.
El [harness](vercel-local-harness.cjs) se ejecutó en un directorio temporal
con `source/` extraído del commit y paquetes de diagnóstico
`@vercel/next@11.0.3`, `@vercel/build-utils@14.9.2`, `@vercel/nft@1.10.0`.
No forma parte de la aplicación ni usa login o despliegue. Los paquetes
transitivos de diagnóstico no tienen lock versionado: esto conserva el ensayo
observado, sin prometer un entorno de diagnóstico reproducible byte a byte.

La prueba no reproduce los ajustes o plataforma reales. Las dos previews alojadas
han fallado y sus registros siguen pendientes de acceso; no se atribuye una causa
al fallo ni se declara completada la aceptación de T03.
