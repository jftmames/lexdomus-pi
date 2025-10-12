from typing import Dict, Any, List, Tuple

def score_eee(analysis: Dict[str, Any]) -> Tuple[float, float, float, List[str]]:
    """
    Devuelve (T, J, P, flags). Placeholder razonable:
    - T: proporción de proposiciones con cita pinpoint
    - J: presencia de regla→hechos→aplicación
    - P: ¿hay ≥1 alternativa razonable?
    """
    props = analysis.get("proposiciones", [])
    cites = [p for p in props if p.get("cita_pinpoint")]
    T = 5.0 * (len(cites)/len(props)) if props else 1.0
    J = 4.0 if analysis.get("tiene_rha") else 2.0
    P = 4.0 if analysis.get("alternativas") else 2.0
    flags = analysis.get("flags", [])
    return T, J, P, flags
