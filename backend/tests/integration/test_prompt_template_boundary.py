"""P1-4 boundary regression tests for legacy PromptTemplate compatibility data."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.adapters.base import Completion, ModelCapability, ProviderRequest
from app.engines.chat.engine import ChatEngine
from app.engines.novel.engine import NovelEngine
from app.engines.novel.generation_preparation import (
    ContinueGenerationInput,
    GenerationTarget,
    PreparedChapterContext,
    PreparedWorkContext,
    freeze_mapping,
    prepare_continue_generation,
)
from app.engines.prompt.assets import PromptAssetLoader
from app.engines.prompt.engine import PromptEngine
from app.engines.shared.summarizer import Summarizer


class _MemoryEngine:
    async def build_memory_context(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(short_term=[], long_term=[])


class _Registry:
    def capabilities(self, *args, **kwargs) -> ModelCapability:  # noqa: ANN002, ANN003
        return ModelCapability(context_window=8192, max_output_tokens=1024)

    def get(self, provider: str):  # noqa: ARG002
        return self

    async def chat(self, assembled, req):  # noqa: ANN001, ARG002
        self.assembled = assembled
        return Completion(content="요약 완료", token_count=2, finish_reason="stop")


def _request() -> ProviderRequest:
    return ProviderRequest(
        provider="fake",
        model_name="fake-1",
        base_url=None,
        api_key=None,
        temperature=0.8,
        max_tokens=256,
        context_window=8192,
    )


def _novel_preparation():  # noqa: ANN202
    return prepare_continue_generation(
        ContinueGenerationInput(
            target=GenerationTarget("owner-1", "work-1", "chapter-1"),
            work=PreparedWorkContext("work-1", "owner-1", "작품", "", "", ()),
            characters=(),
            world=None,
            lore=(),
            prior_summaries=(),
            current_chapter=PreparedChapterContext(
                "chapter-1", "work-1", "owner-1", 1, "", ""
            ),
            instruction="계속",
            target_words=800,
            context_window=8192,
            entry_context_trace=freeze_mapping(
                {"feature_enabled": False, "retrieval_invoked": False}
            ),
        )
    )


def test_repository_defaults_ignore_persisted_legacy_prompt_templates(client) -> None:
    """DB compatibility data cannot become a default architecture prompt source."""

    loader = PromptAssetLoader()
    legacy_templates = (
        ("chat", "chat.default"),
        ("novel", "novel.continue"),
        ("summary", "summary.rolling"),
    )
    for scope, asset_id in legacy_templates:
        asset = loader.load(asset_id)
        response = client.post(
            "/api/v1/prompt-templates",
            json={
                "scope": scope,
                "name": asset_id,
                "body": f"{asset.body}\n\nDB compatibility override attempt",
                "is_default": True,
            },
        )
        assert response.status_code == 201, response.text

    persisted = client.get("/api/v1/prompt-templates")
    assert persisted.status_code == 200, persisted.text
    assert {template["name"] for template in persisted.json()} >= {
        "chat.default",
        "novel.continue",
        "summary.rolling",
    }

    # Loading has no DB-session argument or PromptTemplate dependency.
    assert loader.load("chat.default").body == PromptAssetLoader().load("chat.default").body

    registry = _Registry()
    chat = asyncio.run(
        ChatEngine(PromptEngine(), _MemoryEngine(), registry).assemble_for_chat(
            None,
            chat_id="chat-1",
            character=SimpleNamespace(name="루나", personality="", speech_style=""),
            persona=None,
            world=None,
            lore_entries=[],
            user_message="안녕",
            req=_request(),
        )
    )
    novel = NovelEngine(PromptEngine(), registry).assemble_continue(
        _novel_preparation(), req=_request()
    )
    asyncio.run(
        Summarizer(PromptEngine(), registry).summarize_text(
            source_text="요약할 본문", prev_summary=None, req=_request()
        )
    )

    assert chat.messages[0].content == loader.load("chat.default").body.replace("{{char}}", "루나")
    assert chat.trace["prompt_asset"]["id"] == "chat.default"
    assert novel.messages[0].content == loader.load("novel.continue").body
    assert novel.trace["prompt_asset"]["id"] == "novel.continue"
    assert registry.assembled.messages[0].content == loader.load("summary.rolling").body
    assert registry.assembled.trace["prompt_asset"]["id"] == "summary.rolling"
