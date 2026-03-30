from __future__ import annotations

import json
from typing import Any

from night_journal.config import Settings


class ContentCatalog:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base = settings.automation_dir
        self._persona: dict[str, Any] | None = None

    def _load_persona(self) -> dict[str, Any]:
        if self._persona is None:
            self._persona = json.loads(
                (self.settings.active_persona_dir / 'persona.json').read_text(encoding='utf-8')
            )
        return self._persona

    def load_topic_rules(self) -> dict[str, Any]:
        return self._load_persona()['topics']

    def load_imagery_pool(self) -> dict[str, Any]:
        return self._load_persona()['imagery']

    def load_scene_pool(self) -> dict[str, Any]:
        return self._load_persona()['scenes']

    def load_emotion_pool(self) -> dict[str, Any]:
        return self._load_persona()['emotions']

    def load_event_map_rules(self) -> dict[str, Any]:
        return self._load_persona()['event_map']
