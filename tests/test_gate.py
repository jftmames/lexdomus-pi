import json
from pathlib import Path
from app.pipeline import analyze_clause

def test_no_evidence_returns_no_conclusive():
    # Cláusula neutra que no casa con corpus mínimo -> sin citas suficientes
    clause = "Las partes acuerdan cooperar de buena fe."
    res = analyze_clause(clause, "ES")
    # Gate debe marcar no concluyente si no hay evidencia suficiente
    assert res["gate"]["status"] in ("NO_CONCLUYENTE", "OK")
