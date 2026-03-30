from __future__ import annotations

from pathlib import Path
from typing import Callable


# Tokens whose repeated appearance signals over-use
OVERLAP_TOKENS = ['廊下', '纸窗', '擦剑', '袖中', '主人睡得', '砖缝', '残茶', '灯芯', '帐外']
OVERLAP_THRESHOLD = 4

BANNED_BASE = ['由全真夜札引擎生成', '我嫉妒', '我好恨', '我爱主人', '今夜共有']
MIN_BODY_LENGTH = 220


def quality_check(
    body: str,
    title: str,
    description: str,
    overrides: dict,
    recent_post_paths_fn: Callable[[int], list[Path]],
) -> list[str]:
    """
    Run quality checks on generated content.
    Returns a list of failure reason strings (empty list = pass).
    """
    reasons: list[str] = []

    # 1. Length check
    if len(body.strip()) < MIN_BODY_LENGTH:
        reasons.append('正文过短')

    # 2. Banned terms
    banned = BANNED_BASE + overrides.get('forbid_terms', [])
    for b in banned:
        if b and (b in body or b in title or b in description):
            reasons.append(f'命中禁词:{b}')

    # 3. Title template check
    if title.startswith('夜札：'):
        reasons.append('标题模板化')

    # 4. Description tone check
    if '由' in description and '引擎' in description:
        reasons.append('description 技术味过重')

    # 5. Overlap with recent posts
    try:
        paths = recent_post_paths_fn(3)
        merged_recent = '\n'.join(
            p.read_text(encoding='utf-8')[:700] for p in paths
        )
        overlap = sum(1 for token in OVERLAP_TOKENS if token in body and token in merged_recent)
        if overlap >= OVERLAP_THRESHOLD:
            reasons.append('与近三篇重复度过高')
    except Exception:
        pass

    return reasons


def guard_publish(
    overrides: dict,
    state: dict,
    today_utc_str: str,
) -> None:
    """
    Raise RuntimeError if publishing should be blocked.
    Checks: pause flag, manual-only mode, daily limit.
    """
    if overrides.get('pause_publishing'):
        raise RuntimeError('Publishing paused by manual override.')
    if overrides.get('mode') == 'manual-only':
        raise RuntimeError('Mode is manual-only; timer publish refused.')
    last_day = state.get('meta', {}).get('last_publish_day_utc')
    max_per_day = state.get('scheduler', {}).get('max_posts_per_day', 1)
    if max_per_day > 0 and last_day == today_utc_str:
        raise RuntimeError('Daily publish limit reached; refusing to publish more than one automatic post today.')
