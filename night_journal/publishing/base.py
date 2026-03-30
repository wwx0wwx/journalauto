from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Publisher(ABC):
    @abstractmethod
    def publish(self, title: str, body: str, description: str, category: str) -> tuple[bool, str]:
        """Publish post. Returns (success, message_or_url)."""
        ...
