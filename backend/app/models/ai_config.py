"""AI Config context: ModelConfig, PromptTemplate, ProviderCredential (design 3, 4.2).

Partial-unique defaults (design 4.1-7): one default ModelConfig per user, one
default PromptTemplate per (user, scope). Credentials store encrypted keys only;
plaintext is never serialized (Property 8 / SEC-2).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class ModelConfig(BaseModel):
    __tablename__ = "model_configs"
    __table_args__ = (Index("ix_model_configs_user_default", "user_id", "is_default"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    credential_id: Mapped[str | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(120), default="")
    # purpose lets a user designate a dedicated summary model (design 10.7) without
    # a separate scope column on the wire; default "chat".
    purpose: Mapped[str] = mapped_column(String(20), default="chat")  # chat|summary|novel
    temperature: Mapped[float] = mapped_column(Float, default=0.8)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    context_window: Mapped[int] = mapped_column(Integer, default=8192)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PromptTemplate(BaseModel):
    __tablename__ = "prompt_templates"
    __table_args__ = (Index("ix_prompt_templates_user_scope", "user_id", "scope"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(20), default="chat")  # chat|novel|summary
    name: Mapped[str] = mapped_column(String(200), default="기본")
    body: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class ProviderCredential(BaseModel):
    __tablename__ = "provider_credentials"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    api_key_enc: Mapped[str] = mapped_column(String(4096))  # encrypted (design 4.5)
    label: Mapped[str] = mapped_column(String(120), default="")
