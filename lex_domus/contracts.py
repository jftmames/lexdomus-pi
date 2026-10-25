"""Citation boundary shared by retrieval and policy checks.

Ingestion currently writes flat records. Consumers receive the same provenance
under ``meta``; no missing identity or URL is inferred during normalization.
These structural checks do not establish legal validity or source authenticity.
"""
from typing import Any, Dict, Optional, TypedDict
from urllib.parse import urlsplit


class RequiredCitationMeta(TypedDict):
    doc_id: str
    source: str
    jurisdiction: str
    ref_url: str


class CitationMeta(RequiredCitationMeta, total=False):
    title: str
    family: str
    ref_label: str
    pinpoint: bool
    line_start: int
    line_end: int


class Citation(TypedDict):
    text: str
    meta: CitationMeta


def citation_from_record(record: Any) -> Optional[Citation]:
    """Accept flat or nested records, excluding incomplete/conflicting evidence."""
    if not isinstance(record, dict):
        return None
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    nested = record.get("meta", {})
    if not isinstance(nested, dict):
        return None
    meta = {key: value for key, value in record.items()
            if key not in ("text", "meta", "_score")}
    for key, value in nested.items():
        if key in meta and meta[key] != value:
            return None
        meta[key] = value
    for key in ("doc_id", "source", "jurisdiction", "ref_url"):
        value = meta.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in meta["ref_url"]):
        return None
    try:
        url = urlsplit(meta["ref_url"])
        # Accessing port also validates numeric range/syntax; urlsplit alone does not.
        url.port
        if (url.scheme not in ("http", "https") or not url.hostname
                or url.username is not None or url.password is not None):
            return None
    except ValueError:
        return None
    for key in ("title", "family", "ref_label"):
        if key in meta and not isinstance(meta[key], str):
            return None
    if "pinpoint" in meta and not isinstance(meta["pinpoint"], bool):
        return None
    for key in ("line_start", "line_end"):
        if key in meta and (type(meta[key]) is not int or meta[key] < 1):
            return None
    if "line_start" in meta and "line_end" in meta and meta["line_end"] < meta["line_start"]:
        return None
    return {"text": text, "meta": meta}


def source_is_allowed(policy: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    """An explicit, nonempty list and exact source identity are required."""
    if not isinstance(policy, dict) or not isinstance(meta, dict):
        return False
    sources = policy.get("sources")
    if not isinstance(sources, dict):
        return False
    allowed = sources.get("allowed")
    if not isinstance(allowed, list) or not allowed:
        return False
    if any(not isinstance(source, str) or not source.strip() for source in allowed):
        return False
    source = meta.get("source")
    return isinstance(source, str) and bool(source.strip()) and source in allowed
