from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .models import ContentType


class BaseCompressor:
    content_type = ContentType.UNKNOWN

    def compress(self, text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError


class JsonCompressor(BaseCompressor):
    content_type = ContentType.JSON

    def compress(self, text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
        data = json.loads(text)
        summary = self._summarize(data)
        rendered = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars].rstrip() + "\n... <truncated json summary>"
        return rendered, {"strategy": "schema_and_sample", "json_root": type(data).__name__}

    def _summarize(self, value: Any, depth: int = 0) -> Any:
        if depth >= 3:
            return f"<{type(value).__name__}>"
        if isinstance(value, dict):
            return {
                "_type": "object",
                "_keys": list(value.keys())[:50],
                "_sample": {k: self._summarize(v, depth + 1) for k, v in list(value.items())[:8]},
            }
        if isinstance(value, list):
            return {
                "_type": "array",
                "_length": len(value),
                "_sample": [self._summarize(item, depth + 1) for item in value[:5]],
            }
        if isinstance(value, str):
            return value if len(value) <= 160 else value[:157] + "..."
        return value


class LogCompressor(BaseCompressor):
    content_type = ContentType.LOG

    def compress(self, text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
        lines = text.splitlines()
        level_counts = Counter()
        important: list[str] = []

        for line in lines:
            upper = line.upper()
            for level in ["FATAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG", "TRACE"]:
                if re.search(rf"\b{level}\b", upper):
                    level_counts[level] += 1
                    break
            if any(term in upper for term in ["FATAL", "ERROR", "EXCEPTION", "TRACEBACK", "FAILED", "TIMEOUT"]):
                important.append(line)

        selected = []
        selected.extend(lines[:8])
        if important:
            selected.append("\n# Important lines")
            selected.extend(important[:40])
        selected.append("\n# Tail")
        selected.extend(lines[-8:])

        rendered = "\n".join(dict.fromkeys(selected))
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars].rstrip() + "\n... <truncated log summary>"
        return rendered, {"strategy": "head_errors_tail", "line_count": len(lines), "level_counts": dict(level_counts)}


class CodeCompressor(BaseCompressor):
    content_type = ContentType.CODE

    def compress(self, text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
        # Conservative: code correctness matters, so preserve code unless too large.
        if len(text) <= max_chars:
            return text, {"strategy": "pass_through_code"}

        lines = text.splitlines()
        defs = [line for line in lines if re.match(r"^\s*(def|class|async def|function|export function|const|let|fn)\b", line)]
        imports = [line for line in lines if re.match(r"^\s*(import|from|package|use|require\()\b", line)]

        rendered = "\n".join([
            "# Code outline only. Retrieve original by handle before editing.",
            "# Imports",
            *imports[:40],
            "\n# Definitions",
            *defs[:80],
            "\n# Head",
            *lines[:20],
            "\n# Tail",
            *lines[-20:],
        ])
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars].rstrip() + "\n... <truncated code outline>"
        return rendered, {"strategy": "safe_code_outline", "line_count": len(lines), "definitions_found": len(defs)}


class TextCompressor(BaseCompressor):
    content_type = ContentType.TEXT

    def compress(self, text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if len(text) <= max_chars:
            return text, {"strategy": "pass_through_text"}

        head = paragraphs[:4]
        tail = paragraphs[-2:] if len(paragraphs) > 6 else []
        rendered = "\n\n".join(head + (["... <middle omitted; retrieve original by handle>"] if tail else []) + tail)
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars].rstrip() + "\n... <truncated text summary>"
        return rendered, {"strategy": "head_tail_text", "paragraph_count": len(paragraphs)}


COMPRESSORS = {
    ContentType.JSON: JsonCompressor(),
    ContentType.LOG: LogCompressor(),
    ContentType.CODE: CodeCompressor(),
    ContentType.TEXT: TextCompressor(),
    ContentType.UNKNOWN: TextCompressor(),
}
