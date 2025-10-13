# Marca app/ como paquete y opcionalmente reexporta analyze_clause
try:
    from .pipeline import analyze_clause
except Exception:
    analyze_clause = None

__all__ = ["analyze_clause"]
# Package init for app
