# Paquete para la capa de inquiry/deliberación
try:
    from .inquiry_engine import decompose_clause
except Exception:
    decompose_clause = None

__all__ = ["decompose_clause"]
# Package init for verdiktia
