from __future__ import annotations

import random
from typing import Any


def choose_world_material(
    imagery: dict[str, list[str]],
    scenes: dict[str, list[str]],
    emotions: dict[str, Any],
    state: dict[str, Any],
    overrides: dict[str, Any],
    repeated_phrases: list[str],
) -> tuple[list[str], str, str, str]:
    flat_imagery = imagery['visual'] + imagery['sound'] + imagery['smell'] + imagery['touch']
    recent_used = set(state['continuity'].get('recent_imagery', []))

    motif_clusters = {
        '灯': ['灯', '灯芯', '灯花', '铜灯座', '火星噼剥'],
        '雨': ['雨', '雨丝落檐', '雨后木气', '湿土气'],
        '风': ['风', '风压窗纸', '夜露气'],
        '雪': ['雪', '旧雪', '冬', '寒'],
        '茶': ['茶', '残茶', '茶苦气', '白瓷盏'],
        '剑': ['剑', '冷铁味'],
        '窗': ['窗', '纸窗', '窗纸'],
        '门': ['门', '门闩', '偏门'],
        '夜': ['夜', '更漏'],
    }

    hot_terms = set(repeated_phrases)
    repeated_joined = ' '.join(repeated_phrases)
    for key, cluster in motif_clusters.items():
        if key in repeated_joined:
            hot_terms.update(cluster)

    def allowed_item(x: str) -> bool:
        return x not in recent_used and all(h not in x for h in hot_terms)

    imagery_candidates = [x for x in flat_imagery if allowed_item(x)] or [x for x in flat_imagery if x not in recent_used] or flat_imagery
    chosen_imagery = random.sample(imagery_candidates, k=min(6, len(imagery_candidates)))

    scene_pool = scenes['indoor'] + scenes['semi_outdoor'] + scenes['outer_yard'] + scenes['special']
    recent_scenes = set(state['continuity'].get('recent_scenes', []))
    scene_candidates = [s for s in scene_pool if s not in recent_scenes and all(h not in s for h in hot_terms)] or [s for s in scene_pool if s not in recent_scenes] or scene_pool
    chosen_scene = overrides.get('force_scene') or random.choice(scene_candidates)

    if '窗' in chosen_scene:
        chosen_imagery = [i for i in chosen_imagery if not any(h in i for h in motif_clusters['灯'])][:6] or chosen_imagery
    if any(x in chosen_scene for x in ['偏门', '石阶', '檐', '外院']):
        outdoor_bias = [
            i for i in flat_imagery
            if i in ['门闩', '竹影', '湿土气', '夜露气', '雨后木气', '檐下青砖', '脚步落地极轻', '夜鸟扑翅', '竹叶轻碰']
        ]
        outdoor_bias = [i for i in outdoor_bias if i not in recent_used and all(h not in i for h in hot_terms)] or outdoor_bias
        merged = list(dict.fromkeys((outdoor_bias[:3] + chosen_imagery)))
        chosen_imagery = merged[:6]

    if overrides.get('force_primary_emotion'):
        primary = overrides['force_primary_emotion']
    else:
        primary = random.choice([e for e in emotions['primary'] if e not in state['continuity'].get('recent_emotions', [])[-2:]] or emotions['primary'])
    if overrides.get('force_secondary_emotion'):
        secondary = overrides['force_secondary_emotion']
    else:
        sec_pool = emotions['pairing_hints'].get(primary, emotions['secondary'])
        secondary = random.choice(sec_pool)
    return chosen_imagery, chosen_scene, primary, secondary
