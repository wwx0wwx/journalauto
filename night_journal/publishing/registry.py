from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .base import Publisher
from .hugo import build_hugo, git_push
from .wordpress import WordPressPublisher
from .zhiliu import ZhiliuPublisher


def get_active_publisher(automation_dir: Path) -> Optional[Publisher]:
    """Read publishers.json and return the active Publisher instance, or None."""
    publishers_file = automation_dir / 'publishers.json'
    if not publishers_file.exists():
        return None
    try:
        publishers = json.loads(publishers_file.read_text(encoding='utf-8'))
    except Exception:
        return None
    for p in publishers:
        if not p.get('active'):
            continue
        ptype = p.get('type', '')
        cfg = p.get('config', {})
        if ptype == 'hugo':
            return _HugoPublisher(cfg)
        if ptype == 'wordpress':
            return WordPressPublisher(
                url=cfg.get('xmlrpc_url', ''),
                username=cfg.get('username', ''),
                password=cfg.get('password', ''),
            )
        if ptype == 'zhiliu':
            return ZhiliuPublisher(
                endpoint=cfg.get('endpoint', ''),
                token=cfg.get('token', ''),
                category_id=cfg.get('category_id', ''),
            )
    return None


class _HugoPublisher(Publisher):
    """Thin wrapper so Hugo fits the Publisher interface."""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def publish(self, title: str, body: str, description: str, category: str) -> tuple[bool, str]:
        # Hugo doesn't receive content here — content is written by writer.py before this is called.
        # This is a no-op placeholder; actual build+push is done by application.py.
        return True, 'hugo'
