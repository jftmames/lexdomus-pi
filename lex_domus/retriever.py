from typing import List, Dict, Any

def policy_filter(doc_meta: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    # Filtra por fuente permitida y privacidad básica
    src_ok = any(allow in doc_meta.get('source','') for allow in policy['sources']['allowed'])
    if not src_ok:
        return False
    if policy['privacy']['block_biometrics'] and doc_meta.get('contains_faces', False):
        return False
    return True

def retrieve_candidates(query: str, k: int = 8) -> List[Dict[str, Any]]:
    # TODO: integrar BM25 + denso + rerank
    # Placeholder: retorna lista vacía
    return []
