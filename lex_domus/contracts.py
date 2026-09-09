"""Citation boundary shared by retrieval and policy checks.

Ingestion currently writes flat records. Consumers receive the same provenance
under ``meta``; no missing identity or URL is inferred during normalization.
These structural checks do not establish legal validity or source authenticity.
"""
from typing import Any, Dict, Optional, TypedDict
from urllib.parse import urlsplit
import re
from .policy import source_is_allowed


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
    chunk_id: str
    document_version: str
    source_sha256: str
    normalized_sha256: str
    char_start: int
    char_end: int


class Citation(TypedDict):
    text: str
    meta: CitationMeta


def has_text(value: Any) -> bool:
    return isinstance(value, str) and any(not (char.isspace() or char == "\ufeff") for char in value)


def citation_from_record(record: Any) -> Optional[Citation]:
    """Accept flat or nested records, excluding incomplete/conflicting evidence."""
    if not isinstance(record, dict):
        return None
    text = record.get("text")
    if not has_text(text):
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
    provenance_fields = ("chunk_id", "document_version", "source_sha256", "normalized_sha256", "char_start", "char_end")
    present = [key for key in provenance_fields if meta.get(key) is not None]
    if present:
        if len(present) != len(provenance_fields):
            return None
        if any(not isinstance(meta[key], str) or not re.fullmatch(r"[0-9a-f]{64}", meta[key])
               for key in ("chunk_id", "source_sha256", "normalized_sha256")):
            return None
        if not isinstance(meta["document_version"], str) or not meta["document_version"].strip():
            return None
        if (type(meta["char_start"]) is not int or type(meta["char_end"]) is not int
                or meta["char_start"] < 0 or meta["char_end"] <= meta["char_start"]
                or meta["char_end"] - meta["char_start"] != len(text)):
            return None
    return {"text": text, "meta": meta}
