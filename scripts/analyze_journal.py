#!/usr/bin/env python3
"""全真夜札系统复盘脚本 - 统计发文成功率、高频意象、情绪分布和剧情进度。"""
import json
import os
from pathlib import Path
from collections import Counter

BASE = Path(os.getenv('ENGINE_ROOT', Path(__file__).resolve().parent.parent))
AUTO = BASE / 'automation'
CONTENT = BASE / 'content' / 'posts'
DRAFT = BASE / 'draft_review'

state = json.loads((AUTO / 'world_state.json').read_text())
stats = json.loads((AUTO / 'night_journal_stats.json').read_text())
recent_memories = json.loads((AUTO / 'recent_memories.json').read_text())


def strip_front_matter(text: str) -> str:
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def parse_front_matter(text: str):
    data = {}
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    data[k.strip()] = v.strip().strip('"')
    return data


def latest_posts(limit=10):
    files = sorted(list(CONTENT.glob('*.md')) + list(DRAFT.glob('*.md')), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def title_shape(title: str):
    if any(x in title for x in ['今夜', '夜里', '将明', '子时', '雨里', '雪里']):
        return '时间切片'
    if any(x in title for x in ['不宜', '不可', '未敢', '还在', '更冷', '先受', '近前']):
        return '半句心迹'
    if any(x in title for x in ['替', '把', '挑', '压', '收', '藏']):
        return '动作残片'
    return '极简意象'


posts = latest_posts(12)
word_counts = []
scene_risk = Counter()
term_risk = Counter()
titles = []
descriptions = []
title_shapes = Counter()
for p in posts:
    raw = p.read_text(encoding='utf-8')
    fm = parse_front_matter(raw)
    body = strip_front_matter(raw)
    word_counts.append(len(body))
    titles.append(fm.get('title', ''))
    descriptions.append(fm.get('description', ''))
    for t in ['廊下', '纸窗', '灯', '剑', '茶', '案上', '袖中', '砖缝', '帐外', '薄衾', '铜盆']:
        if t in body:
            term_risk[t] += 1
    for s in state.get('continuity', {}).get('recent_scenes', []):
        scene_risk[s] += 1

print('== 全真夜札系统复盘 ==')
print(f"总发文数: {stats.get('post_count', 0)}")
print(f"成功发文: {stats.get('successful_posts', 0)}")
print(f"失败次数: {stats.get('failed_runs', 0)}")
print(f"修文次数: {stats.get('repaired_runs', 0)}")
print()
print('== 当前世界状态 ==')
relations = state.get('relations', state)  # 兼容新旧格式
owner = relations.get('owner', state.get('owner', {}))
sister = relations.get('sister', state.get('sister', {}))
dims = state.get('character', {}).get('dimensions', state.get('zhen', {}))
print(f"主人疲惫: {owner.get('fatigue', 'N/A')}")
print(f"主人对角色留意: {owner.get('attention_to_zhen', 'N/A')}")
print(f"姐姐压力: {sister.get('pressure', 'N/A')}")
print(f"姐姐归期: {sister.get('eta_days', 'N/A')}")
if dims:
    print('角色维度: ' + '  '.join(f'{k}={v}' for k, v in dims.items()))
print()
print('== 剧情弧线 ==')
for k, v in state.get('story_arcs', {}).items():
    print(f"{k}: stage={v.get('stage')} next_trigger={v.get('next_trigger_post_count')} enabled={v.get('enabled')}")
print()
print('== 最近标题 ==')
for t in titles[:8]:
    print('-', t)
print()
print('== 标题句法分布 ==')
for k, v in title_shapes.most_common():
    print('-', k, v)
print()
print('== 最近 description ==')
for d in descriptions[:8]:
    print('-', d)
print()
if word_counts:
    print('== 字数概况 ==')
    print(f"最近{len(word_counts)}篇平均字数: {sum(word_counts)//len(word_counts)}")
    print(f"最长: {max(word_counts)}  最短: {min(word_counts)}")
    print()
print('== 高频主题 ==')
for k, v in Counter(stats.get('topics', {})).most_common(10):
    print('-', k, v)
print()
print('== 高频场景 ==')
for k, v in Counter(stats.get('scenes', {})).most_common(10):
    print('-', k, v)
print()
print('== 高频主情绪 ==')
for k, v in Counter(stats.get('primary_emotions', {})).most_common(10):
    print('-', k, v)
print()
print('== 高频辅情绪 ==')
for k, v in Counter(stats.get('secondary_emotions', {})).most_common(10):
    print('-', k, v)
print()
print('== 高频意象 Top 15 ==')
for k, v in Counter(stats.get('imagery', {})).most_common(15):
    print('-', k, v)
print()
print('== 最近文本重复风险 ==')
for k, v in term_risk.most_common():
    if v >= 3:
        print('-', k, v)
print()
print('== 近期记忆层 ==')
for item in recent_memories[-8:]:
    print(f"- {item.get('at')} | {item.get('title')} | {item.get('summary')}")
print()
print('== 最近质量失败原因 ==')
for r in stats.get('last_quality_failures', [])[-10:]:
    print('-', r)
print()
print('== 建议观察点 ==')
print('- 若“高频意象”长期被少数几个词占据，应继续扩素材池或提高禁重强度。')
print('- 若“最近标题”过于工整或同型，需加强标题筛选器。')
print('- 若某条剧情弧线长期不推进，应调低 next_trigger 或手动 override。')
print('- 若失败次数上升，优先看日志与质量门禁。')
