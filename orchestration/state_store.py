"""
orchestration/state_store.py — Session state persistence.

Stores session_state + research_state for traceability, idempotence,
and audit. JSON file-backed for the MVP; production would use a DB.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from agents.contracts import SessionState

logger = logging.getLogger("lexdomus.orchestration.state_store")

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "data" / "sessions"


class StateStore:
    """
    Manages session state persistence.

    Each session gets a JSON file in data/sessions/{session_id}.json.
    """

    def __init__(self, base_dir: Path | None = None):
        self._dir = base_dir or STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, SessionState] = {}

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def get(self, session_id: str) -> Optional[SessionState]:
        """Load session state from cache or disk."""
        if session_id in self._cache:
            return self._cache[session_id]

        path = self._path(session_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = SessionState(**data)
            self._cache[session_id] = state
            return state
        except Exception as exc:
            logger.error("Failed to load session %s: %s", session_id, exc)
            return None

    def save(self, state: SessionState) -> None:
        """Persist session state to disk and cache."""
        state.updated_at = datetime.utcnow()
        self._cache[state.session_id] = state
        path = self._path(state.session_id)
        try:
            path.write_text(
                state.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.debug("Saved session %s", state.session_id)
        except Exception as exc:
            logger.error("Failed to save session %s: %s", state.session_id, exc)

    def delete(self, session_id: str) -> None:
        """Remove session state."""
        self._cache.pop(session_id, None)
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return [p.stem for p in self._dir.glob("*.json")]
