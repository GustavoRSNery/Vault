"""Porta de tempo. Injetar o relógio torna testável tudo que expira."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Agora, sempre com timezone."""
        ...
