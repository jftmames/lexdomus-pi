"""
agents/base.py — Base class for all LexDomus agents.

Every agent is a service with:
  - A typed Input contract
  - A typed Output contract
  - A run() method that transforms Input -> Output
  - Logging and error handling
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

logger = logging.getLogger("lexdomus.agents")

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentError(Exception):
    """Raised when an agent fails in a non-recoverable way."""
    pass


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Abstract base for all agents.

    Subclasses must implement:
      - name: str property
      - execute(input) -> output
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier, e.g. 'source-watcher'."""
        ...

    @abstractmethod
    def execute(self, inp: InputT) -> OutputT:
        """Core logic. Must return a valid Output contract."""
        ...

    def run(self, inp: InputT) -> OutputT:
        """
        Public entry point. Wraps execute() with timing and logging.
        """
        logger.info("[%s] START input_type=%s", self.name, type(inp).__name__)
        t0 = time.perf_counter()
        try:
            result = self.execute(inp)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("[%s] DONE %.1fms", self.name, elapsed)
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error("[%s] FAIL %.1fms: %s", self.name, elapsed, exc)
            raise AgentError(f"Agent {self.name} failed: {exc}") from exc
