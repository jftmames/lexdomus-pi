# Planner (Verdiktia) — Descomposición jurídica (Inquiry Graph)

**Tarea:** Dada una cláusula y una jurisdicción objetivo, produce nodos con:
- Pregunta jurídica
- Encaje (fuente positiva: norma, artículo, apartado)
- Principio justificativo (p. ej., proporcionalidad, favor auctoris)
- Evidencias mínimas requeridas
- Hipótesis alternativa razonable

**Nodos mínimos (PI):**
1) Alcance patrimonial (reproducir/distribuir/comunicación/transformación)
2) Derechos morales (paternidad/integridad) – irrenunciables en ES (art. 14 LPI)
3) Temporalidad (plazo vs. duración legal)
4) Territorialidad (ES/EU/worldwide) y trato nacional (Berna art. 5)
5) Modalidades/soportes (enumeración, medios futuros)
6) Remuneración (royalty/forfait) y equilibrio
7) Garantías y originalidad
8) Límites/excepciones (cita, docencia, TDM)
9) Reglas especiales: software/bases de datos

**Salida (JSON):** lista de nodos con `pregunta`, `encaje_ref`, `principio`, `evidencias_requeridas`, `alternativa`.
