from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OverrideState:
    mode: str
    pause_publishing: bool
    raw: dict[str, Any]

    @property
    def is_manual_only(self) -> bool:
        return self.mode == 'manual-only'

    @property
    def is_review_first(self) -> bool:
        return self.mode == 'review-first'

    @property
    def is_auto(self) -> bool:
        return self.mode == 'auto'


def parse_overrides(data: dict[str, Any]) -> OverrideState:
    return OverrideState(
        mode=data.get('mode', 'auto'),
        pause_publishing=bool(data.get('pause_publishing', False)),
        raw=data,
    )
