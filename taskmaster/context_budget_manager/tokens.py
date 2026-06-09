from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """Cheap local token estimate.

    This is intentionally dependency-free. For production, swap this with tiktoken
    or provider-specific token counters.
    """
    if not text:
        return 0

    words = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    # Most English/code-ish text averages around 3-5 chars per token.
    char_estimate = max(1, len(text) // 4)
    word_estimate = max(1, int(len(words) * 0.75))
    return max(char_estimate, word_estimate)
