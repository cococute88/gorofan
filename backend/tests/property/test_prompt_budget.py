"""Property-based tests for PromptEngine (Property 6/7, design 9.18)."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.engines.prompt.engine import AssembleInput, PromptEngine

engine = PromptEngine()


@settings(max_examples=80, deadline=None)
@given(
    user_msg=st.text(min_size=0, max_size=2000),
    history_texts=st.lists(st.text(min_size=0, max_size=500), max_size=10),
    context_window=st.integers(min_value=512, max_value=32000),
    max_tokens=st.integers(min_value=64, max_value=4000),
)
def test_property7_token_budget(user_msg, history_texts, context_window, max_tokens):
    # Property 6 precondition
    if context_window < max_tokens:
        context_window, max_tokens = max_tokens + 256, max_tokens

    class _Msg:
        def __init__(self, c):
            self.content = c
            self.role = "user"
            self.id = id(c)

    inp = AssembleInput(
        template_body="system instructions",
        history=[_Msg(t) for t in history_texts],
        user_message=user_msg or None,
        context_window=context_window,
        max_tokens=max_tokens,
        safety_ratio=0.08,
    )
    assembled = engine.assemble(inp)
    # Property 7: assembled prompt tokens never exceed the context window.
    assert assembled.token_count <= context_window


@settings(max_examples=40, deadline=None)
@given(user_msg=st.text(min_size=1, max_size=300))
def test_user_message_preserved_when_fits(user_msg):
    inp = AssembleInput(
        template_body="sys",
        user_message=user_msg,
        context_window=8192,
        max_tokens=512,
    )
    assembled = engine.assemble(inp)
    # The user message content should appear among the assembled messages.
    joined = " ".join(m.content for m in assembled.messages)
    assert user_msg.strip()[:10] in joined or user_msg in joined
