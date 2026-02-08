"""
orchestration/session.py — Session manager for creating and tracking sessions.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from agents.contracts import Jurisdiction, SessionState
from orchestration.state_store import StateStore


class SessionManager:
    """Creates and manages deliberation sessions."""

    def __init__(self, store: StateStore | None = None):
        self._store = store or StateStore()

    def create(
        self,
        clause: str,
        jurisdiction: Jurisdiction = Jurisdiction.ES,
        instrument_type: str = "clausula",
    ) -> SessionState:
        """Create a new session with a unique ID."""
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        state = SessionState(
            session_id=session_id,
            jurisdiction=jurisdiction,
            clause=clause,
            instrument_type=instrument_type,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._store.save(state)
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._store.get(session_id)

    def save(self, state: SessionState) -> None:
        self._store.save(state)

    def list_sessions(self) -> list[str]:
        return self._store.list_sessions()
