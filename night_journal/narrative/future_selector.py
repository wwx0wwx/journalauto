from __future__ import annotations

import random
from typing import Any


def maybe_future_fragment(
    overrides: dict[str, Any],
    future_fragments: list[dict[str, Any]],
    story_arcs: dict[str, Any],
) -> str:
    if overrides.get('force_future_id'):
        for f in future_fragments:
            if f['id'] == overrides['force_future_id']:
                return f'今夜你隐约预感：{f["summary"]} 这件事迟早会来。只把这种预感化作暗影，不要直白预告。'
    active: list[dict[str, Any]] = []
    for f in future_fragments:
        arc = story_arcs.get(f['arc'])
        if arc and arc['stage'] >= f['stage'] - 1:
            active.append(f)
    if active and random.random() < 0.22:
        pick = random.choices(active, weights=[x.get('weight', 1) for x in active], k=1)[0]
        return f'今夜你隐约预感：{pick["summary"]} 这件事迟早会来。只把这种预感化作暗影，不要直白预告。'
    return ''
