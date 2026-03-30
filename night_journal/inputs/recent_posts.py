from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from night_journal.config import Settings


@dataclass
class RecentPost:
    path: Path
    title: str
    description: str
    body: str


def strip_front_matter(text: str) -> str:
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def parse_front_matter(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    data[k.strip()] = v.strip().strip('"')
    return data


def extract_repeated_phrases(texts: list[str]) -> list[str]:
    phrases: list[str] = []
    patterns = [
        r'廊下', r'门外', r'帐内', r'垂帘', r'砖缝', r'擦了', r'替主人挡', r'袖中',
        r'指节', r'更冷', r'天色', r'属下还在', r'灯', r'剑', r'茶', r'纸窗',
        r'案上', r'眉间', r'风', r'雨', r'寒'
    ]
    merged = '\n'.join(texts)
    for p in patterns:
        if len(re.findall(p, merged)) >= 2:
            phrases.append(p)
    return phrases[:16]


def recent_posts(settings: Settings, limit: int = 8) -> list[RecentPost]:
    files = sorted(
        list(settings.content_dir.glob('*.md')) + list(settings.draft_review_dir.glob('*.md')),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    posts: list[RecentPost] = []
    for path in files:
        raw = path.read_text(encoding='utf-8')
        fm = parse_front_matter(raw)
        posts.append(
            RecentPost(
                path=path,
                title=fm.get('title', ''),
                description=fm.get('description', ''),
                body=strip_front_matter(raw),
            )
        )
    return posts


def build_recent_context(settings: Settings, limit: int = 6) -> tuple[list[str], list[str], list[str], list[str]]:
    posts = recent_posts(settings, limit=limit)
    texts = [p.body[:1500] for p in posts]
    titles = [p.title for p in posts if p.title]
    descs = [p.description for p in posts if p.description]
    repeated = extract_repeated_phrases(texts)
    return texts, repeated, titles, descs
