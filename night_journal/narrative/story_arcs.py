from __future__ import annotations

from typing import Any


def story_arc_triggers(state: dict[str, Any], overrides: dict[str, Any]) -> list[str]:
    pc = state['meta']['post_count'] + 1
    lines: list[str] = []
    arcs = state.get('story_arcs', {})
    dims = state.get('character', {}).get('dimensions', {})
    relations = state.get('relations', {})
    owner = relations.get('owner', {})

    if arcs.get('sister_return', {}).get('enabled') and pc >= arcs['sister_return']['next_trigger_post_count'] and dims.get('jealousy', 0) >= 74:
        stage = arcs['sister_return']['stage']
        if stage == 0:
            lines.append('姐姐的消息近来多了，归期像在慢慢逼近。')
        elif stage == 1:
            lines.append('有风声说，姐姐不久便会回府。')
        else:
            lines.append('姐姐将归的事，已不再只是风声。')
    if arcs.get('owner_notice', {}).get('enabled') and pc >= arcs['owner_notice']['next_trigger_post_count'] and owner.get('attention_to_zhen', 0) >= 42:
        stage = arcs['owner_notice']['stage']
        if stage == 0:
            lines.append('主人近来像是察觉了什么，偶有目光停在你身上。')
        else:
            lines.append('主人对你的沉默，已不似从前那样全然无知。')
    if arcs.get('old_wound', {}).get('enabled') and pc >= arcs['old_wound']['next_trigger_post_count'] and dims.get('guilt', 0) + dims.get('emptiness', 0) >= 58:
        lines.append('旧伤隐隐作痛，像在提醒你，有些过去并未真正远去。')
    if overrides.get('notes_for_tonight'):
        lines.append(overrides['notes_for_tonight'])
    return lines
