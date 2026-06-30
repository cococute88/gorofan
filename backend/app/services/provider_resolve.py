"""Resolve a ModelConfig (+credential) into a ProviderRequest (design 13.10).

Decrypts the API key only at call time, in backend memory (SEC-2). Validates
ModelConfig.context_window against adapter capability (design 13.10).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ProviderRequest
from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import NotFound, ValidationAppError
from app.core.security import decrypt_secret
from app.models.ai_config import ModelConfig, ProviderCredential


async def resolve_provider_request(
    session: AsyncSession,
    settings: Settings,
    registry: ProviderRegistry,
    *,
    user_id: str,
    model_config_id: str | None,
    purpose: str = "chat",
) -> ProviderRequest:
    cfg = await _resolve_config(session, user_id, model_config_id, purpose)
    api_key: str | None = None
    if cfg.credential_id:
        cred = await session.get(ProviderCredential, cfg.credential_id)
        if cred is not None and cred.user_id == user_id:
            api_key = decrypt_secret(settings, cred.api_key_enc)

    cap = registry.capabilities(cfg.provider, cfg.model_name)
    context_window = cfg.context_window or cap.context_window
    if context_window > cap.context_window and cap.context_window > 0:
        # trust capability as the authority for known providers
        context_window = cap.context_window
    if context_window < cfg.max_tokens:
        raise ValidationAppError("context_window < max_tokens", {"inv": "INV-6"})

    return ProviderRequest(
        provider=cfg.provider,
        model_name=cfg.model_name,
        base_url=cfg.base_url,
        api_key=api_key,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        context_window=context_window,
    )


async def _resolve_config(
    session: AsyncSession, user_id: str, model_config_id: str | None, purpose: str
) -> ModelConfig:
    if model_config_id:
        cfg = await session.get(ModelConfig, model_config_id)
        if cfg is None or cfg.user_id != user_id:
            raise NotFound("ModelConfig not found")
        return cfg
    # purpose-specific default (summary) preferred, then global default
    if purpose == "summary":
        stmt = select(ModelConfig).where(
            ModelConfig.user_id == user_id, ModelConfig.purpose == "summary"
        ).limit(1)
        cfg = (await session.execute(stmt)).scalars().first()
        if cfg is not None:
            return cfg
    stmt = (
        select(ModelConfig)
        .where(ModelConfig.user_id == user_id, ModelConfig.is_default.is_(True))
        .limit(1)
    )
    cfg = (await session.execute(stmt)).scalars().first()
    if cfg is None:
        stmt2 = select(ModelConfig).where(ModelConfig.user_id == user_id).limit(1)
        cfg = (await session.execute(stmt2)).scalars().first()
    if cfg is None:
        raise NotFound("No ModelConfig configured. Add one in settings.")
    return cfg
