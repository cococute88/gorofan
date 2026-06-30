"""AI Config DTOs (design 6). Credentials are masked on output (Property 8)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedOut


class ModelConfigCreate(BaseModel):
    provider: str
    model_name: str
    base_url: str | None = None
    credential_id: str | None = None
    label: str = ""
    purpose: str = "chat"  # chat|summary|novel
    temperature: float = 0.8
    max_tokens: int = Field(default=1024, ge=1)
    context_window: int = Field(default=8192, ge=1)
    is_default: bool = False


class ModelConfigOut(TimestampedOut):
    user_id: str
    provider: str
    model_name: str
    base_url: str | None
    credential_id: str | None
    label: str
    purpose: str
    temperature: float
    max_tokens: int
    context_window: int
    is_default: bool


class PromptTemplateCreate(BaseModel):
    scope: str = "chat"
    name: str = "기본"
    body: str = ""
    is_default: bool = False


class PromptTemplateOut(TimestampedOut):
    user_id: str
    scope: str
    name: str
    body: str
    is_default: bool


class CredentialCreate(BaseModel):
    provider: str
    api_key: str = Field(min_length=1)
    label: str = ""


class CredentialOut(TimestampedOut):
    """Masked output — never returns plaintext key (Property 8)."""

    user_id: str
    provider: str
    label: str
    masked_key: str


class ProviderInfo(BaseModel):
    provider: str
    models: list[str] = []
