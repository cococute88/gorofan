"""AIConfigService (design 8.2). Masks credentials on output (Property 8)."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import ValidationAppError
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.ai_config import ModelConfig, PromptTemplate, ProviderCredential
from app.schemas.ai_config import (
    CredentialCreate,
    ModelConfigCreate,
    PromptTemplateCreate,
)


class AIConfigService:
    def __init__(self, settings: Settings, registry: ProviderRegistry) -> None:
        self.settings = settings
        self.registry = registry

    # ----- model configs -----
    async def create_model_config(
        self, session: AsyncSession, user_id: str, dto: ModelConfigCreate
    ) -> ModelConfig:
        cap = self.registry.capabilities(dto.provider, dto.model_name)
        if dto.context_window > cap.context_window and cap.context_window > 0:
            raise ValidationAppError(
                "context_window exceeds model capability",
                {"capability": cap.context_window},
            )
        if dto.context_window < dto.max_tokens:
            raise ValidationAppError("context_window < max_tokens", {"inv": "INV-6"})
        cfg = ModelConfig(user_id=user_id, **dto.model_dump())
        session.add(cfg)
        await session.flush()
        if dto.is_default:
            await self._unset_other_defaults(session, user_id, cfg.id)
        await session.commit()
        await session.refresh(cfg)
        return cfg

    async def list_model_configs(self, session: AsyncSession, user_id: str) -> list[ModelConfig]:
        stmt = select(ModelConfig).where(ModelConfig.user_id == user_id)
        return list((await session.execute(stmt)).scalars().all())

    async def _unset_other_defaults(self, session, user_id, keep_id) -> None:  # noqa: ANN001
        await session.execute(
            update(ModelConfig)
            .where(ModelConfig.user_id == user_id, ModelConfig.id != keep_id)
            .values(is_default=False)
        )

    # ----- prompt templates -----
    async def create_template(
        self, session: AsyncSession, user_id: str, dto: PromptTemplateCreate
    ) -> PromptTemplate:
        tpl = PromptTemplate(user_id=user_id, **dto.model_dump())
        session.add(tpl)
        if dto.is_default:
            await session.flush()
            await session.execute(
                update(PromptTemplate)
                .where(
                    PromptTemplate.user_id == user_id,
                    PromptTemplate.scope == dto.scope,
                    PromptTemplate.id != tpl.id,
                )
                .values(is_default=False)
            )
        await session.commit()
        await session.refresh(tpl)
        return tpl

    async def list_templates(self, session: AsyncSession, user_id: str) -> list[PromptTemplate]:
        stmt = select(PromptTemplate).where(PromptTemplate.user_id == user_id)
        return list((await session.execute(stmt)).scalars().all())

    # ----- credentials -----
    async def create_credential(
        self, session: AsyncSession, user_id: str, dto: CredentialCreate
    ) -> dict:
        enc = encrypt_secret(self.settings, dto.api_key)
        cred = ProviderCredential(
            user_id=user_id, provider=dto.provider, api_key_enc=enc, label=dto.label
        )
        session.add(cred)
        await session.commit()
        await session.refresh(cred)
        return self.to_masked(cred)

    async def list_credentials(self, session: AsyncSession, user_id: str) -> list[dict]:
        stmt = select(ProviderCredential).where(ProviderCredential.user_id == user_id)
        rows = list((await session.execute(stmt)).scalars().all())
        return [self.to_masked(c) for c in rows]

    def to_masked(self, cred: ProviderCredential) -> dict:
        try:
            plaintext = decrypt_secret(self.settings, cred.api_key_enc)
        except ValueError:
            plaintext = ""
        return {
            "id": cred.id,
            "user_id": cred.user_id,
            "provider": cred.provider,
            "label": cred.label,
            "masked_key": mask_secret(plaintext),
            "created_at": cred.created_at,
            "updated_at": cred.updated_at,
        }

    def list_providers(self) -> list[str]:
        return self.registry.list_providers()
