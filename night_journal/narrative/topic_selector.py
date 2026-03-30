from __future__ import annotations

import random
from typing import Any


def choose_topic(rules: dict[str, Any], state: dict[str, Any], overrides: dict[str, Any]) -> tuple[str, str]:
    if overrides.get('force_topic'):
        return overrides['force_topic'], overrides['force_topic']
    all_topics: list[tuple[str, str]] = []
    for cat in rules['categories']:
        for prompt in cat['prompts']:
            all_topics.append((cat['name'], prompt))
    recent = set(state.get('continuity', {}).get('recent_topics', [])[-3:])
    forbids = set(overrides.get('forbid_topics', []))
    candidates = [t for t in all_topics if t[0] not in recent and t[0] not in forbids] or all_topics
    return random.choice(candidates)
