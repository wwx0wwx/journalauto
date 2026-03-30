#!/usr/bin/env python3
"""config.py — 配置加载与全局常量"""
import json, pathlib

def _load_env(path=None):
    if path is None:
        path = str(pathlib.Path(__file__).resolve().parent.parent / '.env')
    env = {}
    try:
        for line in pathlib.Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

_env = _load_env()

BASE        = pathlib.Path(_env.get('ENGINE_ROOT', '/opt/blog-src'))
AUTO        = BASE / 'automation'
CONTENT     = BASE / 'content' / 'posts'
DRAFT_REVIEW= BASE / 'draft_review'
OUT         = pathlib.Path(_env.get('BLOG_OUTPUT_DIR', '/var/www/example.com'))
LOG         = BASE / 'logs'

API_KEY  = _env.get('OPENAI_API_KEY', '')
BASE_URL = _env.get('OPENAI_BASE_URL', 'https://ai.dooo.ng/v1/chat/completions')
MODEL    = _env.get('OPENAI_MODEL', 'gpt-5.4')

# 确保运行时目录存在
DRAFT_REVIEW.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)


def load_json(name: str) -> object:
    """从 automation/ 读取 JSON 文件。"""
    return json.loads((AUTO / name).read_text(encoding='utf-8'))


def save_json(path: pathlib.Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
