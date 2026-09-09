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
de producción. La construcción Docker queda pendiente de CI. Véase el alcance
y los límites en [T03-dependencies.md](../T03-dependencies.md).
