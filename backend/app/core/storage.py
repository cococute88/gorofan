"""File storage abstraction (design 8.9).

MVP: LocalFileStorage. Swap to S3 via the same Protocol (FUT-3). Upload validation
(size/MIME/magic bytes) lives in the service layer (design 8.9.3 / SEC-8).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class StoredFile:
    path: str
    url: str
    size: int
    content_type: str


class StorageBackend(Protocol):
    async def save(self, path: str, data: bytes, content_type: str) -> StoredFile: ...
    async def open(self, path: str) -> AsyncIterator[bytes]: ...
    async def delete(self, path: str) -> None: ...
    def url_for(self, path: str) -> str: ...


class LocalFileStorage:
    def __init__(self, base_dir: str, public_base: str = "/media") -> None:
        self.base_dir = base_dir
        self.public_base = public_base
        os.makedirs(base_dir, exist_ok=True)

    def _abs(self, path: str) -> str:
        return os.path.join(self.base_dir, path)

    async def save(self, path: str, data: bytes, content_type: str) -> StoredFile:
        abs_path = self._abs(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)
        return StoredFile(path=path, url=self.url_for(path), size=len(data), content_type=content_type)

    async def open(self, path: str) -> AsyncIterator[bytes]:
        with open(self._abs(path), "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    async def delete(self, path: str) -> None:
        try:
            os.remove(self._abs(path))
        except FileNotFoundError:
            pass

    def url_for(self, path: str) -> str:
        return f"{self.public_base}/{path}"


def build_storage_backend(backend: str, media_root: str) -> StorageBackend:
    # Extension point: 's3' -> S3Storage with presigned url_for (FUT-3).
    return LocalFileStorage(media_root)
