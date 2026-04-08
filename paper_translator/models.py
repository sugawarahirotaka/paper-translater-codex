from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PageArtifact:
    page_number: int
    text: str
    text_path: Path
    image_path: Path


@dataclass(slots=True)
class ChunkInput:
    chunk_index: int
    page_numbers: list[int]
    source_text: str
    image_paths: list[Path]


@dataclass(slots=True)
class AuditResult:
    coverage: str
    issues: list[str]


@dataclass(slots=True)
class ChunkTranslation:
    chunk_index: int
    page_numbers: list[int]
    english_title: str
    translated_markdown: str
    audit: AuditResult | None
    warnings: list[str] = field(default_factory=list)

