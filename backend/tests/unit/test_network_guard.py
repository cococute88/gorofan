"""No real HTTP transport may run in an automated provider test."""
import httpx
import pytest


def test_unmocked_sync_http_is_blocked_before_network() -> None:
    with httpx.Client() as client, pytest.raises(AssertionError, match="external HTTP blocked in tests"):
        client.get("https://network-guard.invalid/check")


async def test_unmocked_async_http_is_blocked_before_network() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(AssertionError, match="external HTTP blocked in tests"):
            await client.get("https://network-guard.invalid/check")
