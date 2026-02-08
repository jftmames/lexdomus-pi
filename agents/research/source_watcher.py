"""
agents/research/source_watcher.py — Source-Watcher (BOE / EUR-Lex)

Detects changes in official sources: new consolidation, modification,
derogation, correction.  Fires deprecation + re-ingest + alert.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List

from agents.base import BaseAgent
from agents.contracts import (
    ReformEvent,
    ReformType,
    SourceOrigin,
    SourceWatcherInput,
    SourceWatcherOutput,
)

logger = logging.getLogger("lexdomus.agents.source_watcher")

ROOT = Path(__file__).resolve().parents[2]
REFORMS_REPORT = ROOT / "data" / "status" / "reforms_report.json"
CORPUS_DIR = ROOT / "data" / "corpus"


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    if path.exists():
        h.update(path.read_bytes())
    return h.hexdigest()


def _detect_reform_type(old_hash: str, new_hash: str, filename: str) -> ReformType:
    """Heuristic reform-type detection based on filename patterns."""
    name = filename.lower()
    if not old_hash:
        return ReformType.NEW_CONSOLIDATION
    if "deroga" in name:
        return ReformType.DEROGATION
    if "correc" in name:
        return ReformType.CORRECTION
    return ReformType.MODIFICATION


def _source_origin_from_filename(filename: str) -> SourceOrigin:
    name = filename.lower()
    if name.startswith("es_"):
        return SourceOrigin.BOE
    if name.startswith("eu_"):
        return SourceOrigin.EUR_LEX
    if name.startswith("us_"):
        return SourceOrigin.USC
    if "berne" in name or "wipo" in name:
        return SourceOrigin.WIPO
    return SourceOrigin.OTHER


class SourceWatcherAgent(BaseAgent[SourceWatcherInput, SourceWatcherOutput]):
    @property
    def name(self) -> str:
        return "source-watcher"

    def execute(self, inp: SourceWatcherInput) -> SourceWatcherOutput:
        """
        Compares current corpus file hashes against last known baseline.
        Produces ReformEvent for each detected change.
        """
        events: List[ReformEvent] = []
        errors: List[str] = []

        # Load previous baseline
        baseline: dict = {}
        if REFORMS_REPORT.exists():
            try:
                baseline = json.loads(REFORMS_REPORT.read_text(encoding="utf-8"))
                if isinstance(baseline, list):
                    baseline = {e.get("source_id", ""): e for e in baseline}
            except Exception as exc:
                errors.append(f"Failed to load baseline: {exc}")

        # Scan corpus files
        if not CORPUS_DIR.exists():
            errors.append(f"Corpus dir not found: {CORPUS_DIR}")
            return SourceWatcherOutput(events=events, errors=errors)

        allowed_origins = set(inp.sources_to_watch) if inp.sources_to_watch else None

        for fpath in sorted(CORPUS_DIR.glob("*")):
            if fpath.is_dir():
                continue
            origin = _source_origin_from_filename(fpath.name)
            if allowed_origins and origin not in allowed_origins:
                continue

            current_hash = _hash_file(fpath)
            source_id = fpath.stem
            prev = baseline.get(source_id, {})
            prev_hash = prev.get("hash", "") if isinstance(prev, dict) else ""

            if current_hash != prev_hash:
                reform_type = _detect_reform_type(prev_hash, current_hash, fpath.name)
                events.append(
                    ReformEvent(
                        source_id=source_id,
                        source_origin=origin,
                        reform_type=reform_type,
                        old_version=prev_hash or None,
                        new_version=current_hash,
                        diff_hint=f"File changed: {fpath.name}",
                    )
                )

        return SourceWatcherOutput(events=events, errors=errors)
