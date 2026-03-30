from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from night_journal.config import Settings


class StateStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base = settings.automation_dir

    def _read_json(self, name: str) -> Any:
        return json.loads((self.base / name).read_text(encoding='utf-8'))

    def _write_json(self, name: str, data: Any) -> None:
        (self.base / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def load_world_state(self) -> dict[str, Any]:
        return self._read_json('world_state.json')

    def load_recent_memories(self) -> list[dict[str, Any]]:
        return self._read_json('recent_memories.json')

    def load_stats(self) -> dict[str, Any]:
        return self._read_json('night_journal_stats.json')

    def load_overrides(self) -> dict[str, Any]:
        return self._read_json('manual_overrides.json')

    def load_future_fragments(self) -> list[dict[str, Any]]:
        return self._read_json('future_fragments.json')

    def load_memory_anchors(self) -> list[dict[str, Any]]:
        return self._read_json('memory_anchors.json')

    def save_world_state(self, data: dict[str, Any]) -> None:
        self._write_json('world_state.json', data)

    def save_recent_memories(self, data: list[dict[str, Any]]) -> None:
        self._write_json('recent_memories.json', data)

    def save_stats(self, data: dict[str, Any]) -> None:
        self._write_json('night_journal_stats.json', data)
