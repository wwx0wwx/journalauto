from __future__ import annotations

import random
from typing import Any


def maybe_memory(
    primary_emotion: str,
    overrides: dict[str, Any],
    anchors: list[dict[str, Any]],
    recent_memories: list[dict[str, Any]],
    rules: dict[str, Any],
) -> str:
    if overrides.get('force_memory_id'):
        for a in anchors:
            if a['id'] == overrides['force_memory_id']:
                return f'今夜某一瞬让你想起：{a["summary"]}。请让这段记忆像水面倒影一样掠过，不要整篇写成回忆录。'
    if recent_memories and random.random() < 0.25:
        pick = random.choice(recent_memories[-5:])
        return f'近来的某件事又在今夜浮上心头：{pick["summary"]}。只让它淡淡掠过。'
    if random.random() < rules.get('memory_trigger_probability', 0.2):
        filtered = [a for a in anchors if primary_emotion in ''.join(a.get('emotion', [])) or primary_emotion in ''.join(a.get('trigger_tags', []))]
        pool = filtered or anchors
        pick = random.choices(pool, weights=[a.get('weight', 1) for a in pool], k=1)[0]
        return f'今夜某一瞬让你想起：{pick["summary"]}。请让这段记忆像水面倒影一样掠过，不要整篇写成回忆录。'
    return ''
