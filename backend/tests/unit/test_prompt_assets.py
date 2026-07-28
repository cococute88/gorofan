"""Regression tests for repository-managed creative prompt assets."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.base import Completion, ModelCapability, ProviderRequest
from app.engines.chat.engine import ChatEngine
from app.engines.novel.engine import ChapterContext, NovelEngine
from app.engines.prompt.assets import (
    PROMPT_ASSET_ROOT,
    PromptAssetLoader,
    PromptAssetNotFoundError,
    PromptAssetVersionMismatchError,
)
from app.engines.prompt.engine import PromptEngine
from app.engines.shared.summarizer import Summarizer

# These frozen test fixtures capture the three bodies exactly as they existed
# before the P1-3 asset migration; they are not runtime prompt sources.
CHAT_BODY = (
    "당신은 {{char}}라는 캐릭터로서 사용자와 대화한다. 캐릭터의 성격과 말투를 일관되게 "
    "유지하고, 세계관과 기억을 존중하며 자연스러운 한국어로 응답한다."
)
NOVEL_BODY = (
    "당신은 숙련된 소설가다. 주어진 세계관·등장인물·이전 줄거리에 일관되게, 몰입감 있는 "
    "한국어 산문으로 다음 분량을 이어쓴다. 시점과 문체를 유지하고 갑작스러운 설정 변경을 피한다."
)
SUMMARY_BODY = (
    "당신은 장편 서사의 기록자다. 아래 대화/본문을 한국어로 간결하게 요약한다. "
    "등장인물의 결정·감정 변화·중요한 사실·미해결 떡밥을 보존하되 군더더기는 제거한다. "
    "이전 요약이 있으면 누적해 갱신한다."
)


class _MemoryEngine:
    async def build_memory_context(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(short_term=[], long_term=[])


class _Registry:
    def __init__(self) -> None:
        self.assembled = None

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


@pytest.mark.parametrize(
    ("asset_id", "relative_path", "expected_body"),
    [
        ("chat.default", Path("chat/default.v1.md"), CHAT_BODY),
        ("novel.continue", Path("novel/continue.v1.md"), NOVEL_BODY),
        ("summary.rolling", Path("shared/rolling-summary.v1.md"), SUMMARY_BODY),
    ],
)
def test_assets_load_as_exact_utf8_versioned_bodies(
    asset_id: str, relative_path: Path, expected_body: str
) -> None:
    loader = PromptAssetLoader()

    asset = loader.load(asset_id, expected_version="v1")

    assert loader.path_for(asset_id) == PROMPT_ASSET_ROOT / relative_path
    assert asset.asset_id == asset_id
    assert asset.version == "v1"
    assert asset.body == expected_body
    assert asset.sha256 == sha256(expected_body.encode("utf-8")).hexdigest()


def test_asset_lookup_is_deterministic_and_failures_are_explicit(tmp_path) -> None:
    loader = PromptAssetLoader()

    assert loader.load("chat.default") == loader.load("chat.default")
    with pytest.raises(PromptAssetVersionMismatchError, match="requested version 'v2'"):
        loader.load("chat.default", expected_version="v2")
    with pytest.raises(PromptAssetNotFoundError, match="Unknown prompt asset id"):
        loader.path_for("writer.draft")
    with pytest.raises(PromptAssetNotFoundError, match="is missing"):
        PromptAssetLoader(root=tmp_path).load("chat.default")


@pytest.mark.asyncio
async def test_chat_default_uses_the_asset_and_preserves_custom_template_override() -> None:
    registry = _Registry()
    engine = ChatEngine(PromptEngine(), _MemoryEngine(), registry)

    assembled = await engine.assemble_for_chat(
        None,
        chat_id="chat-1",
        character=SimpleNamespace(name="루나", personality="", speech_style=""),
        persona=None,
        world=None,
        lore_entries=[],
        user_message="안녕",
        req=_request(),
    )
    custom = await engine.assemble_for_chat(
        None,
        chat_id="chat-1",
        character=None,
        persona=None,
        world=None,
        lore_entries=[],
        user_message="안녕",
        req=_request(),
        template_body="사용자 제공 템플릿",
    )

    assert assembled.messages[0].content == CHAT_BODY.replace("{{char}}", "루나")
    assert assembled.trace["prompt_asset"]["id"] == "chat.default"
    assert assembled.trace["prompt_asset"]["version"] == "v1"
    assert custom.messages[0].content == "사용자 제공 템플릿"
    assert "prompt_asset" not in custom.trace


def test_novel_continue_uses_the_asset_and_records_trace_identity() -> None:
    registry = _Registry()
    ctx = ChapterContext(
        work=object(),
        current_chapter=SimpleNamespace(content_text=""),
        prior_summaries=[],
        characters=[],
        world=None,
        lore_entries=[],
    )

    assembled = NovelEngine(PromptEngine(), registry).assemble_continue(
        ctx,
        instruction="계속",
        req=_request(),
    )

    assert assembled.messages[0].content == NOVEL_BODY
    assert assembled.trace["prompt_asset"]["id"] == "novel.continue"
    assert assembled.trace["prompt_asset"]["version"] == "v1"


@pytest.mark.asyncio
async def test_summary_uses_the_asset_and_records_trace_identity() -> None:
    registry = _Registry()
    summarizer = Summarizer(PromptEngine(), registry)

    result = await summarizer.summarize_text(
        source_text="요약할 본문",
        prev_summary=None,
        req=_request(),
    )

    assert result == "요약 완료"
    assert registry.assembled.messages[0].content == SUMMARY_BODY
    assert registry.assembled.trace["prompt_asset"]["id"] == "summary.rolling"
    assert registry.assembled.trace["prompt_asset"]["version"] == "v1"
