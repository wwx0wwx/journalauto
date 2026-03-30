from __future__ import annotations

import json
import re

from .llm_client import api_chat


def generate_title_and_description(
    base_url: str,
    api_key: str,
    model: str,
    body: str,
    recent_titles: list[str],
    recent_descs: list[str],
    max_retries: int = 3,
    timeout: int = 150,
) -> tuple[str, str]:
    prompt = f'''根据下面这篇夜札正文，为博客生成一个标题和一条 description。要求：标题不要用固定模板；标题句法要主动分散，轮换使用"极简意象 / 半句心迹 / 动作残片 / 时间切片"四类，不要连续几篇都像同一种短句；description 不要写技术味提示，要像页边的一点轻注、心情、缘由，或极短摘要；标题 4-12 字为宜，description 16-36 字为宜；避免与最近这些标题/description 太像。\n最近标题：{recent_titles}\n最近description：{recent_descs}\n\n请严格用 JSON 输出：{{"title":"...","description":"..."}}\n\n正文：\n{body}\n'''
    raw = api_chat(
        base_url,
        api_key,
        model,
        [
            {'role': 'system', 'content': '你是一个审美克制的中文文学编辑。只输出合法 JSON。'},
            {'role': 'user', 'content': prompt},
        ],
        temperature=0.78,
        max_tokens=220,
        max_retries=max_retries,
        timeout=timeout,
    )
    m = re.search(r'\{.*\}', raw, re.S)
    if not m:
        return '灯下未眠', '这一页，是在灯将尽时留下的。'
    try:
        obj = json.loads(m.group(0))
        return obj.get('title', '灯下未眠'), obj.get('description', '这一页，是在灯将尽时留下的。')
    except Exception:
        return '灯下未眠', '这一页，是在灯将尽时留下的。'
