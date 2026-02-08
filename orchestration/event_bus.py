"""
orchestration/event_bus.py — In-process event bus for agent coordination.

Supports:
  - publish/subscribe by event type
  - synchronous dispatch (for traceability)
  - event history for audit
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("lexdomus.orchestration.event_bus")


@dataclass
class Event:
    """An event on the bus."""
    event_type: str
    payload: Any
    source_agent: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type}:{self.source_agent}:{int(self.timestamp * 1000)}"


Subscriber = Callable[[Event], None]


class EventBus:
    """
    Simple in-process event bus.

    In production, this would be backed by Redis Streams, RabbitMQ, or similar.
    For the MVP, synchronous dispatch provides full traceability.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Subscriber]] = {}
        self._history: List[Event] = []

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        """Register a handler for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed to '%s': %s", event_type, handler)

    def publish(self, event: Event) -> None:
        """Dispatch event to all subscribers synchronously."""
        self._history.append(event)
        handlers = self._subscribers.get(event.event_type, [])
        logger.info(
            "Event '%s' from '%s' -> %d handlers",
            event.event_type,
            event.source_agent,
            len(handlers),
        )
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    "Handler failed for event '%s': %s",
                    event.event_type,
                    exc,
                )

    def history(self, event_type: Optional[str] = None) -> List[Event]:
        """Return event history, optionally filtered by type."""
        if event_type:
            return [e for e in self._history if e.event_type == event_type]
        return list(self._history)

    def clear(self) -> None:
        """Clear history (for testing)."""
        self._history.clear()
