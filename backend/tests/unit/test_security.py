"""Unit tests for crypto/masking (Property 8 / SEC)."""
from __future__ import annotations

from app.config import Settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret


def _settings() -> Settings:
    return Settings(APP_SECRET_KEY="unit-test-secret-key-0123456789abcdef")


def test_encrypt_decrypt_roundtrip():
    s = _settings()
    plaintext = "sk-proj-supersecret-abcd1234"
    enc = encrypt_secret(s, plaintext)
    assert enc != plaintext
    assert decrypt_secret(s, enc) == plaintext


def test_mask_never_reveals_full_key():
    masked = mask_secret("sk-proj-supersecret-abcd1234")
    assert masked.endswith("1234")
    assert "supersecret" not in masked
