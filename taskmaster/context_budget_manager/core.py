from __future__ import annotations

from pathlib import Path

from .compressors import COMPRESSORS
from .detectors import detect_content_type
from .models import CompressionResult
from .store import OriginalStore
from .tokens import estimate_tokens


class ContextBudgetManager:
    """Compress context while preserving originals behind retrieval handles."""

    def __init__(self, db_path: str | Path | None = None, default_max_chars: int = 4_000) -> None:
        from taskmaster import CACHE_DIR
        self.store = OriginalStore(db_path or (CACHE_DIR / "context.db"))
        self.default_max_chars = default_max_chars

    def compress(
        self,
        text: str,
        *,
        source_name: str | None = None,
        max_chars: int | None = None,
    ) -> CompressionResult:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        content_type = detect_content_type(text, source_name=source_name)
        original_tokens = estimate_tokens(text)
        handle = self.store.put(text, content_type.value, source_name, {"source_name": source_name})

        compressor = COMPRESSORS[content_type]
        compressed_body, metadata = compressor.compress(text, max_chars or self.default_max_chars)

        header = (
            f"<compressed_context handle='{handle}' type='{content_type.value}' "
            f"original_tokens='{original_tokens}'>\n"
            f"To inspect the exact original content, retrieve handle: {handle}\n"
            f"</compressed_context>\n\n"
        )
        compressed_text = header + compressed_body
        compressed_tokens = estimate_tokens(compressed_text)
        ratio = compressed_tokens / max(1, original_tokens)

        return CompressionResult(
            handle=handle,
            content_type=content_type,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=ratio,
            compressed_text=compressed_text,
            metadata=metadata,
        )

    def retrieve(self, handle: str) -> str:
        return self.store.get(handle)

    def stats(self) -> dict[str, object]:
        return self.store.stats()

    def prune(self, max_age_seconds: float) -> int:
        return self.store.prune(max_age_seconds)

