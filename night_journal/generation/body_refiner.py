from __future__ import annotations

from .llm_client import api_chat


def refine_body(base_url: str, api_key: str, model: str, body: str, max_retries: int = 3, timeout: int = 150) -> str:
    prompt = f'''请将下面这篇夜札做一次"冷处理式润色"。要求：保留原意，不要改剧情；去掉明显解释感、模板感、口水句；若句子太满，就削薄；增强清冷、克制、贴身的质感；不要变成长篇排比；只输出润色后的正文。\n\n正文：\n{body}\n'''
    return api_chat(
        base_url,
        api_key,
        model,
        [
            {'role': 'system', 'content': '你是一个极其克制的文学润色者，擅长把句子削薄。'},
            {'role': 'user', 'content': prompt},
        ],
        temperature=0.4,
        max_tokens=900,
        max_retries=max_retries,
        timeout=timeout,
    )
