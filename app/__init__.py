# Marca app/ como paquete y opcionalmente reexporta analyze_clause
# app/pipeline.py (al inicio)
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .pipeline import analyze_clause
except Exception:
    analyze_clause = None

__all__ = ["analyze_clause"]
# Package init for app
