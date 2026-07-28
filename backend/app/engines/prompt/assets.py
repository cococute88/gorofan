"""Repository-managed prompt asset loading.

Prompt bodies are architecture-owned files under ``backend/prompts``.  The
allow-list below is the only runtime lookup surface: callers use a stable asset
identifier, never an arbitrary filesystem path or a database body.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

PROMPT_ASSET_ROOT = Path(__file__).resolve().parents[3] / "prompts"


@dataclass(frozen=True)
class _AssetDefinition:
    version: str
    relative_path: Path


@dataclass(frozen=True)
class PromptAsset:
    """An immutable, versioned prompt body resolved from the repository."""

    asset_id: str
    version: str
    body: str
    sha256: str


class PromptAssetError(RuntimeError):
    """Base error for deterministic prompt asset lookup failures."""


class PromptAssetNotFoundError(PromptAssetError):
    """Raised when an identifier is unknown or its registered file is absent."""


class PromptAssetVersionMismatchError(PromptAssetError):
    """Raised when a caller requests a version other than the registered one."""


_ASSET_DEFINITIONS: dict[str, _AssetDefinition] = {
    "chat.default": _AssetDefinition("v1", Path("chat/default.v1.md")),
    "novel.continue": _AssetDefinition("v1", Path("novel/continue.v1.md")),
    "summary.rolling": _AssetDefinition("v1", Path("shared/rolling-summary.v1.md")),
}


class PromptAssetLoader:
    """Resolve allow-listed UTF-8 prompt assets from the packaged asset root."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or PROMPT_ASSET_ROOT

    def path_for(self, asset_id: str) -> Path:
        """Return the deterministic repository-relative location for ``asset_id``."""

        try:
            definition = _ASSET_DEFINITIONS[asset_id]
        except KeyError as exc:
            raise PromptAssetNotFoundError(f"Unknown prompt asset id: {asset_id!r}") from exc
        return self._root / definition.relative_path

    def load(self, asset_id: str, *, expected_version: str | None = None) -> PromptAsset:
        """Load a registered UTF-8 prompt body with explicit version validation."""

        try:
            definition = _ASSET_DEFINITIONS[asset_id]
        except KeyError as exc:
            raise PromptAssetNotFoundError(f"Unknown prompt asset id: {asset_id!r}") from exc
        if expected_version is not None and expected_version != definition.version:
            raise PromptAssetVersionMismatchError(
                f"Prompt asset {asset_id!r} has version {definition.version!r}, "
                f"not requested version {expected_version!r}"
            )

        path = self._root / definition.relative_path
        try:
            body = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise PromptAssetNotFoundError(
                f"Prompt asset {asset_id!r} version {definition.version!r} is missing at {path}"
            ) from exc
        return PromptAsset(
            asset_id=asset_id,
            version=definition.version,
            body=body,
            sha256=sha256(body.encode("utf-8")).hexdigest(),
        )
