# Paquete para el scoring y logging EEE
try:
    from .scorer import score_eee
except Exception:
    score_eee = None

try:
    from .logger import append_log
except Exception:
    append_log = None

__all__ = ["score_eee", "append_log"]
# Package init for metrics_eee
