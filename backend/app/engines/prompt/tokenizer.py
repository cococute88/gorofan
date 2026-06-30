"""Token counting abstraction (design 9.4, 9.7).

Exact tokenizers are unavailable for many remote providers, so MVP uses an
approximate counter (chars/4 heuristic, adjusted for CJK density) with a
provider-specific safety ratio applied by the BudgetManager. Synchronous work is
cheap here; heavier tokenizers would be offloaded to a threadpool (design 8.6.1).
"""
from __future__ import annotations


class Tokenizer:
    """Approximate, deterministic token counter."""

    def count(self, text: str) -> int:
        if not text:
            return 0
        # CJK characters are ~1 token each; latin ~ chars/4. Blend heuristically.
        cjk = sum(1 for ch in text if "\u3000" <= ch <= "\u9fff" or "\uac00" <= ch <= "\ud7a3")
        other = len(text) - cjk
        return max(1, cjk + (other // 4) + 1)

    def safety_ratio(self, hint: str) -> float:
        return 0.02 if hint.startswith("tiktoken") else 0.08


default_tokenizer = Tokenizer()
