"""Token budget management + truncation (design 9.7, 9.9).

Guarantees Property 7: assembled token_count <= context_window. user_message and
system blocks are protected (design 9.9).
"""
from __future__ import annotations

from app.engines.prompt.blocks import BudgetResult, PromptBlock
from app.engines.prompt.tokenizer import Tokenizer

MIN_PROMPT_BUDGET = 256
MIN_PROTECTED_RETAINED_TOKENS = MIN_PROMPT_BUDGET // 2


class PromptBudgetError(ValueError):
    """The mandatory prompt blocks cannot fit the available context budget."""


class BudgetManager:
    def __init__(self, tokenizer: Tokenizer) -> None:
        self.tok = tokenizer

    def compute_budget(self, context_window: int, max_tokens: int, safety_ratio: float) -> int:
        # Property 6 precondition is validated by the engine before calling.
        safety = int(context_window * safety_ratio + 0.999)
        budget = context_window - max_tokens - safety
        return max(budget, MIN_PROMPT_BUDGET)

    def fit(self, blocks: list[PromptBlock], budget: int) -> BudgetResult:
        result = BudgetResult(budget=budget)
        # 1) reserve protected blocks (priority >= 1000 user/instruction, and system==100)
        protected = [b for b in blocks if b.priority >= 1000 or b.kind == "system"]
        optional = [b for b in blocks if b not in protected]

        used = 0
        for b in protected:
            used += b.token_count
        # Protected may itself exceed budget. Reduce the largest eligible block
        # first, then continue across other protected/truncatable blocks until
        # the aggregate fits. A single pass is insufficient when both the
        # current Chapter and the generation instruction are large.
        if used > budget:
            self._trim_protected(protected, budget, result)
            used = sum(b.token_count for b in protected)

        available = budget - used
        # 2) include optional by priority desc until budget exhausted
        for b in sorted(optional, key=lambda x: x.priority, reverse=True):
            if b.token_count <= available:
                result.included.append(b)
                available -= b.token_count
            elif b.truncatable and available > 0:
                before = b.token_count
                kept = self._trim_to(b, available)
                result.included.append(kept)
                result.trimmed.append((kept, before - kept.token_count))
                available = 0
            else:
                result.dropped.append(b)

        result.included.extend(protected)
        result.final_tokens = sum(b.token_count for b in result.included)
        if result.final_tokens > budget:
            raise PromptBudgetError(
                "Prompt blocks cannot fit the available context budget"
            )
        return result

    def _trim_to(self, block: PromptBlock, max_tokens: int) -> PromptBlock:
        # Approximate trim: keep proportional prefix on word boundary.
        if block.token_count <= max_tokens or block.token_count == 0:
            return block
        ratio = max_tokens / block.token_count
        cut = max(1, int(len(block.content) * ratio))
        text = block.content[:cut].rsplit(" ", 1)[0] if " " in block.content[:cut] else block.content[:cut]
        block.content = text
        block.token_count = self.tok.count(text)
        return block

    def _trim_protected(
        self, protected: list[PromptBlock], budget: int, result: BudgetResult
    ) -> None:
        # Keep the existing largest-first/minimum-retention policy, but repeat it
        # when more than one protected block must yield space.
        used = sum(block.token_count for block in protected)
        while used > budget:
            candidates = [
                block
                for block in protected
                if block.truncatable
                and block.token_count > MIN_PROTECTED_RETAINED_TOKENS
            ]
            if not candidates:
                raise PromptBudgetError(
                    "Mandatory prompt blocks cannot fit the available context budget"
                )
            target = max(candidates, key=lambda block: block.token_count)
            others = used - target.token_count
            allowed = max(MIN_PROTECTED_RETAINED_TOKENS, budget - others)
            before = target.token_count
            self._trim_to(target, allowed)
            trimmed_tokens = before - target.token_count
            if trimmed_tokens <= 0:
                raise PromptBudgetError(
                    "Protected prompt block could not be reduced to the context budget"
                )
            result.trimmed.append((target, trimmed_tokens))
            used -= trimmed_tokens
