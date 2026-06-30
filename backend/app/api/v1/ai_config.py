"""AI config router: model-configs, prompt-templates, credentials, providers (design 6.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_state
from app.models.user import User
from app.schemas.ai_config import (
    CredentialCreate,
    CredentialOut,
    ModelConfigCreate,
    ModelConfigOut,
    PromptTemplateCreate,
    PromptTemplateOut,
    ProviderInfo,
)

router = APIRouter()


def _svc(state):  # noqa: ANN001
    return state.ai_config_service


@router.get("/model-configs", response_model=list[ModelConfigOut])
async def list_model_configs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).list_model_configs(db, user.id)


@router.post("/model-configs", response_model=ModelConfigOut, status_code=status.HTTP_201_CREATED)
async def create_model_config(dto: ModelConfigCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).create_model_config(db, user.id, dto)


@router.get("/prompt-templates", response_model=list[PromptTemplateOut])
async def list_templates(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).list_templates(db, user.id)


@router.post("/prompt-templates", response_model=PromptTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(dto: PromptTemplateCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).create_template(db, user.id, dto)


@router.get("/credentials", response_model=list[CredentialOut])
async def list_credentials(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).list_credentials(db, user.id)


@router.post("/credentials", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(dto: CredentialCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), state=Depends(get_state)):
    return await _svc(state).create_credential(db, user.id, dto)


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(state=Depends(get_state)):
    return [ProviderInfo(provider=p) for p in _svc(state).list_providers()]
