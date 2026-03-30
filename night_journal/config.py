from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    engine_root: Path
    automation_dir: Path
    content_dir: Path
    draft_review_dir: Path
    output_dir: Path
    log_dir: Path
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_model_fast: str
    persona_md_path: Path
    active_persona_dir: Path


def _resolve_active_persona_dir(automation_dir: Path) -> Path:
    active_file = automation_dir / 'active_persona'
    personas_dir = automation_dir / 'personas'
    if active_file.exists() and personas_dir.exists():
        name = active_file.read_text(encoding='utf-8').strip()
        candidate = personas_dir / name
        if candidate.is_dir():
            return candidate
    return automation_dir


def _load_api_settings(automation_dir: Path) -> dict:
    """Read automation/api_settings.json, return empty dict if missing."""
    p = automation_dir / 'api_settings.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def load_settings(env_root: Optional[Path] = None) -> Settings:
    root = Path(env_root or os.getenv('ENGINE_ROOT', Path(__file__).resolve().parent.parent)).resolve()
    automation_dir = root / 'automation'
    active_persona_dir = _resolve_active_persona_dir(automation_dir)
    persona_md_env = os.getenv('PERSONA_MD', '')
    persona_md_path = Path(persona_md_env) if persona_md_env else active_persona_dir / 'persona.md'

    api = _load_api_settings(automation_dir)

    return Settings(
        engine_root=root,
        automation_dir=automation_dir,
        content_dir=root / 'content' / 'posts',
        draft_review_dir=root / 'draft_review',
        output_dir=Path(os.getenv('BLOG_OUTPUT_DIR', '/var/www/example.com')).resolve(),
        log_dir=Path(os.getenv('LOG_DIR', root / 'logs')).resolve(),
        openai_api_key=os.getenv('OPENAI_API_KEY', api.get('api_key', '')),
        openai_base_url=os.getenv('OPENAI_BASE_URL', api.get('base_url', 'https://ai.dooo.ng/v1/chat/completions')),
        openai_model=os.getenv('OPENAI_MODEL', api.get('model', 'gpt-5.4')),
        openai_model_fast=os.getenv('OPENAI_MODEL_FAST', api.get('model_fast', api.get('model', 'gpt-5.4'))),
        persona_md_path=persona_md_path,
        active_persona_dir=active_persona_dir,
    )
