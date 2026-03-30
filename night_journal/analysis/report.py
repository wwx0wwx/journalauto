from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..inputs.recent_posts import strip_front_matter, parse_front_matter


OVERLAP_TERMS = ['廊下', '纸窗', '灯', '剑', '茶', '案上', '袖中', '砖缝', '帐外', '薄衾', '铜盆']


def title_shape(title: str) -> str:
    if any(x in title for x in ['今夜', '夜里', '将明', '子时', '雨里', '雪里']):
        return '时间切片'
    if any(x in title for x in ['不宜', '不可', '未敢', '还在', '更冷', '先受', '近前']):
        return '半句心迹'
    if any(x in title for x in ['替', '把', '挑', '压', '收', '藏']):
        return '动作残片'
    return '极简意象'


def latest_post_files(content_dir: Path, draft_dir: Path, limit: int = 12) -> list[Path]:
    files = sorted(
        list(content_dir.glob('*.md')) + list(draft_dir.glob('*.md')),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:limit]


def analyze(
    state: dict[str, Any],
    stats: dict[str, Any],
    recent_memories: list[dict[str, Any]],
    content_dir: Path,
    draft_dir: Path,
    post_limit: int = 12,
) -> dict[str, Any]:
    """
    Run a full analysis pass over journal state and recent posts.
    Returns a structured report dict.
    """
    posts = latest_post_files(content_dir, draft_dir, limit=post_limit)
    word_counts: list[int] = []
    term_risk: Counter = Counter()
    titles: list[str] = []
    descriptions: list[str] = []
    title_shapes: Counter = Counter()
    scene_risk: Counter = Counter()

    for p in posts:
        try:
            raw = p.read_text(encoding='utf-8')
        except Exception:
            continue
        fm = parse_front_matter(raw)
        body = strip_front_matter(raw)
        word_counts.append(len(body))
        t = fm.get('title', '')
        titles.append(t)
        descriptions.append(fm.get('description', ''))
        title_shapes[title_shape(t)] += 1
        for term in OVERLAP_TERMS:
            if term in body:
                term_risk[term] += 1

    for s in state.get('continuity', {}).get('recent_scenes', []):
        scene_risk[s] += 1

    return {
        'summary': {
            'post_count': stats.get('post_count', 0),
            'successful_posts': stats.get('successful_posts', 0),
            'failed_runs': stats.get('failed_runs', 0),
            'repaired_runs': stats.get('repaired_runs', 0),
        },
        'world_state': {
            'owner_fatigue': state.get('owner', {}).get('fatigue'),
            'owner_attention': state.get('owner', {}).get('attention_to_zhen'),
            'sister_pressure': state.get('sister', {}).get('pressure'),
            'sister_renown': state.get('sister', {}).get('renown'),
            'zhen_jealousy': state.get('zhen', {}).get('jealousy'),
            'zhen_longing': state.get('zhen', {}).get('longing'),
            'zhen_restraint': state.get('zhen', {}).get('restraint'),
            'zhen_emptiness': state.get('zhen', {}).get('emptiness'),
        },
        'story_arcs': {
            k: {'stage': v.get('stage'), 'enabled': v.get('enabled')}
            for k, v in state.get('story_arcs', {}).items()
        },
        'titles': titles[:8],
        'descriptions': descriptions[:8],
        'title_shapes': dict(title_shapes.most_common()),
        'word_counts': {
            'count': len(word_counts),
            'avg': sum(word_counts) // len(word_counts) if word_counts else 0,
            'max': max(word_counts) if word_counts else 0,
            'min': min(word_counts) if word_counts else 0,
        },
        'top_topics': dict(Counter(stats.get('topics', {})).most_common(10)),
        'top_scenes': dict(Counter(stats.get('scenes', {})).most_common(10)),
        'top_primary_emotions': dict(Counter(stats.get('primary_emotions', {})).most_common(10)),
        'top_secondary_emotions': dict(Counter(stats.get('secondary_emotions', {})).most_common(10)),
        'top_imagery': dict(Counter(stats.get('imagery', {})).most_common(15)),
        'term_risk': dict(term_risk.most_common()),
        'recent_memories': [
            {'at': m.get('at'), 'title': m.get('title'), 'summary': m.get('summary')}
            for m in recent_memories[-8:]
        ],
        'last_quality_failures': stats.get('last_quality_failures', [])[-10:],
        'suggestions': [
            '若高频意象长期被少数词占据，应扩素材池或提高禁重强度。',
            '若最近标题过于同型，需加强标题筛选器。',
            '若某条剧情弧线长期不推进，应调低 next_trigger 或手动 override。',
            '若失败次数上升，优先看日志与质量门禁。',
        ],
    }


def print_report(report: dict) -> None:
    """Print a human-readable analysis report to stdout."""
    s = report['summary']
    print('== 全真夜札系统复盘 ==')
    print(f"总发文数: {s['post_count']}  成功: {s['successful_posts']}  失败: {s['failed_runs']}  修文: {s['repaired_runs']}")
    print()
    w = report['world_state']
    print('== 当前世界状态 ==')
    print(f"主人疲惫: {w['owner_fatigue']}  留意: {w['owner_attention']}")
    print(f"姐姐压力: {w['sister_pressure']}  名声: {w['sister_renown']}")
    print(f"全真 嫉妒:{w['zhen_jealousy']} 渴望:{w['zhen_longing']} 克制:{w['zhen_restraint']} 空寂:{w['zhen_emptiness']}")
    print()
    print('== 剧情弧线 ==')
    for k, v in report['story_arcs'].items():
        print(f"  {k}: stage={v['stage']} enabled={v['enabled']}")
    print()
    print('== 最近标题 ==')
    for t in report['titles']:
        print('-', t)
    print()
    print('== 标题句法分布 ==')
    for k, v in report['title_shapes'].items():
        print(f'  {k}: {v}')
    print()
    wc = report['word_counts']
    if wc['count']:
        print(f"== 字数概况 ==  平均:{wc['avg']}  最长:{wc['max']}  最短:{wc['min']}")
        print()
    print('== 高频主题 ==')
    for k, v in report['top_topics'].items():
        print(f'  {k}: {v}')
    print()
    print('== 高频意象 Top 15 ==')
    for k, v in report['top_imagery'].items():
        print(f'  {k}: {v}')
    print()
    print('== 文本重复风险 ==')
    for k, v in report['term_risk'].items():
        if v >= 3:
            print(f'  {k}: {v}')
    print()
    print('== 最近质量失败原因 ==')
    for r in report['last_quality_failures']:
        print('-', r)
    print()
    print('== 建议观察点 ==')
    for s in report['suggestions']:
        print('-', s)
