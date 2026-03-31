"""
Purpose: pytest test suite for DSS network policy enforcement logic.
Responsibilities:
    - Verify global mode allows all IPs.
    - Verify LAN mode allows RFC-1918 addresses and blocks public IPs.
    - Verify allowlist mode permits exact IP matches and CIDR membership.
    - Verify allowlist mode blocks IPs not in the list.
    - Verify mode switching at runtime.
    - Verify invalid mode raises ValueError.
Dependencies: pytest, asyncio, dss.server.app.services.network_policy
"""

import pytest

from dss.server.app.services.network_policy import NetworkPolicy


@pytest.mark.asyncio
class TestNetworkPolicy:
    async def test_global_allows_all(self):
        policy = NetworkPolicy(mode="global")
        assert await policy.is_allowed("8.8.8.8") is True
        assert await policy.is_allowed("192.168.1.1") is True
        assert await policy.is_allowed("10.0.0.1") is True

    async def test_lan_allows_rfc1918(self):
        policy = NetworkPolicy(mode="lan")
        assert await policy.is_allowed("192.168.0.1") is True
        assert await policy.is_allowed("10.0.0.100") is True
        assert await policy.is_allowed("172.16.5.5") is True
        assert await policy.is_allowed("127.0.0.1") is True

    async def test_lan_blocks_public(self):
        policy = NetworkPolicy(mode="lan")
        assert await policy.is_allowed("8.8.8.8") is False
        assert await policy.is_allowed("1.1.1.1") is False

    async def test_allowlist_exact_match(self):
        policy = NetworkPolicy(mode="allowlist", allowed_ips=["203.0.113.5"])
        assert await policy.is_allowed("203.0.113.5") is True
        assert await policy.is_allowed("203.0.113.6") is False

    async def test_allowlist_cidr_match(self):
        policy = NetworkPolicy(mode="allowlist", allowed_ips=["10.10.0.0/16"])
        assert await policy.is_allowed("10.10.1.100") is True
        assert await policy.is_allowed("10.11.0.1") is False

    async def test_allowlist_blocks_unlisted(self):
        policy = NetworkPolicy(mode="allowlist", allowed_ips=["192.168.1.50"])
        assert await policy.is_allowed("192.168.1.51") is False

    async def test_mode_switching(self):
        policy = NetworkPolicy(mode="global")
        assert await policy.is_allowed("8.8.8.8") is True
        await policy.set_mode("lan")
        assert await policy.is_allowed("8.8.8.8") is False

    async def test_invalid_mode_raises(self):
        policy = NetworkPolicy(mode="global")
        with pytest.raises(ValueError):
            await policy.set_mode("unknown")

    async def test_add_remove_allowed_ip(self):
        policy = NetworkPolicy(mode="allowlist")
        await policy.add_allowed_ip("5.5.5.5")
        assert await policy.is_allowed("5.5.5.5") is True
        await policy.remove_allowed_ip("5.5.5.5")
        assert await policy.is_allowed("5.5.5.5") is False

    async def test_replace_allowed_ips(self):
        policy = NetworkPolicy(mode="allowlist", allowed_ips=["1.2.3.4"])
        await policy.set_allowed_ips(["9.9.9.9"])
        assert await policy.is_allowed("1.2.3.4") is False
        assert await policy.is_allowed("9.9.9.9") is True
