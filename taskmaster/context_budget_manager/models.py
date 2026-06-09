from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    JSON = "json"
    LOG = "log"
    CODE = "code"
    TEXT = "text"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompressionResult:
    handle: str
    content_type: ContentType
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compressed_text: str
    metadata: dict[str, Any]

    @property
    def saved_tokens(self) -> int:
        return max(0, self.original_tokens - self.compressed_tokens)
