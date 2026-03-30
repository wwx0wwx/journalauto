from __future__ import annotations

from pathlib import Path
from typing import Any


def build_prompt(
    state: dict[str, Any],
    overrides: dict[str, Any],
    rules: dict[str, Any],
    recent_memories: list[dict[str, Any]],
    events: list[str],
    topic: str,
    memory_block: str,
    future_block: str,
    repeated_phrases: list[str],
    chosen_imagery: list[str],
    chosen_scene: str,
    primary: str,
    secondary: str,
    arc_lines: list[str],
    persona_md_path: Path,
    persona_cfg: dict[str, Any],
) -> str:
    template = persona_md_path.read_text(encoding='utf-8')

    repeated_text = '\u3001'.join(repeated_phrases) if repeated_phrases else '\u65e0\u660e\u663e\u91cd\u590d'
    arc_text = ' '.join(arc_lines) if arc_lines else '\u4eca\u591c\u6ca1\u6709\u65b0\u7684\u547d\u6570\u843d\u4e0b\uff0c\u53ea\u662f\u65e7\u5fc3\u4e8b\u5728\u6162\u6162\u53d1\u9175\u3002'
    recent_mem_text = '\uff1b'.join([m['summary'] for m in recent_memories[-3:]]) if recent_memories else '\u8fd1\u6765\u65e0\u65b0\u7684\u53ef\u8ffd\u5fc6\u7247\u6bb5\u3002'
    forbid_text = '\u3001'.join(overrides.get('forbid_terms', [])) if overrides.get('forbid_terms') else '\u65e0\u989d\u5916\u7981\u8bcd'

    meta = state.get('meta', {})
    relations = state.get('relations', {})
    dims = state.get('character', {}).get('dimensions', {})
    dim_labels = persona_cfg.get('dimension_labels', {})

    # Build relation state lines
    relation_lines = []
    for rel_name, rel_data in relations.items():
        label_map = {
            'owner': '\u4e3b\u4eba',
            'sister': '\u59d0\u59d0',
        }
        label = label_map.get(rel_name, rel_name)
        parts = [f'{k} {v}' for k, v in rel_data.items()]
        relation_lines.append(f'- {label}\u72b6\u6001\uff1a{"\uff0c".join(parts)}')
    relation_state = '\n'.join(relation_lines)

    # Build dimension state lines
    dim_parts = []
    for k, v in dims.items():
        label = dim_labels.get(k, k)
        dim_parts.append(f'{label} {v}/100')
    dimension_state = f'- \u4f60\u7684\u60c5\u7eea\uff1a{"\uff0c".join(dim_parts)}' if dim_parts else ''

    variables = {
        'character_name': persona_cfg.get('name', '\u89d2\u8272'),
        'character_traits': persona_cfg.get('traits', ''),
        'address_rules': persona_cfg.get('address_rules', ''),
        'writing_rules': persona_cfg.get('writing_rules', ''),
        'current_season': meta.get('current_season', ''),
        'current_watch': meta.get('current_watch', ''),
        'weather': meta.get('weather', ''),
        'relation_state': relation_state,
        'dimension_state': dimension_state,
        'last_summary': state.get('continuity', {}).get('last_summary', ''),
        'recent_mem_text': recent_mem_text,
        'events_text': ' '.join(events),
        'arc_text': arc_text,
        'topic': topic,
        'chosen_scene': chosen_scene,
        'imagery_text': '\u3001'.join(chosen_imagery),
        'primary': primary,
        'secondary': secondary,
        'memory_block': memory_block,
        'future_block': future_block,
        'repeated_text': repeated_text,
        'forbid_text': forbid_text,
        'target_word_count': rules.get('target_word_count', 380),
    }

    return template.format_map(variables)
