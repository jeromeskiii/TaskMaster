from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ContentType

CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".cpp", ".c",
    ".h", ".cs", ".php", ".rb", ".swift", ".kt", ".sql", ".sh", ".bash",
}

LOG_PATTERNS = [
    re.compile(r"\b(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL)\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}"),
    re.compile(r"Traceback \(most recent call last\):"),
]


def detect_content_type(text: str, source_name: str | None = None) -> ContentType:
    stripped = text.strip()
    if not stripped:
        return ContentType.UNKNOWN

    if source_name:
        suffix = Path(source_name).suffix.lower()
        if suffix in CODE_EXTENSIONS:
            return ContentType.CODE
        if suffix in {".json", ".jsonl"}:
            return ContentType.JSON
        if suffix in {".log", ".out"}:
            return ContentType.LOG

    if _looks_like_json(stripped):
        return ContentType.JSON

    if any(pattern.search(stripped) for pattern in LOG_PATTERNS):
        return ContentType.LOG

    if _looks_like_code(stripped):
        return ContentType.CODE

    return ContentType.TEXT


def _looks_like_json(text: str) -> bool:
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return False
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def _looks_like_code(text: str) -> bool:
    code_markers = ["def ", "class ", "import ", "export ", "function ", "const ", "let ", "fn ", "package "]
    marker_hits = sum(marker in text for marker in code_markers)
    punctuation_density = sum(ch in text for ch in "{}();[]=<>" ) / max(1, len(text))
    return marker_hits >= 2 or punctuation_density > 0.035
