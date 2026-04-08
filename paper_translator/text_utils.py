from __future__ import annotations

import re
import unicodedata


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip() + "\n"


def tail_excerpt(text: str, limit: int = 1200) -> str:
    compact = text.strip()
    if len(compact) <= limit:
        return compact
    return compact[-limit:]


def compact_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def slugify_title(title: str, fallback: str = "translated-paper") -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or fallback

