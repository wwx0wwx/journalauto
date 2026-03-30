from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GeneratedDraft:
    title: str
    description: str
    body: str
    category: str = ''
    path: Path | None = None


@dataclass
class QualityReport:
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class PublishResult:
    mode: str
    path: Path | None = None
    built: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    ok: bool
    stage: str
    message: str = ''
    data: dict[str, Any] = field(default_factory=dict)
