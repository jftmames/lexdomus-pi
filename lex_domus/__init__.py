# Hace que lex_domus sea un paquete y reexporta lo esencial
from .rag_pipeline import load_policy, source_required_answer  # y cualquier helper que uses
try:
    from .retriever import retrieve_candidates
except Exception:
    retrieve_candidates = None

# Opcional: si tienes este módulo en el repo
try:
    from .flagger import detect_flags, propose_alternative
except Exception:
    detect_flags = None
    propose_alternative = None

__all__ = [
    "load_policy",
    "source_required_answer",
    "retrieve_candidates",
    "detect_flags",
    "propose_alternative",
]
# Package init for lex_domus
