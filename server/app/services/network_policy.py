"""
Purpose: DSS Coordinator network policy enforcement — global, LAN, and allowlist modes.
Responsibilities:
    - Track current network mode (global / lan / allowlist).
    - Maintain an admin-configurable set of allowed IP addresses or CIDR ranges.
    - Provide a guard method used at peer registration and per-request to validate origin IP.
    - Detect LAN addresses using RFC-1918 prefix matching.
Dependencies: asyncio, ipaddress
"""

import asyncio
import ipaddress
from typing import List, Set


_LAN_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

NETWORK_MODES = {"global", "lan", "allowlist"}


class NetworkPolicy:
    """Enforces DSS coordinator network access policy."""

    def __init__(self, mode: str = "global", allowed_ips: List[str] = None) -> None:
        """
        Initialise with a network mode and optional list of allowed IPs/CIDRs.
        Defaults to global mode (all IPs accepted).
        """
        self._mode = mode if mode in NETWORK_MODES else "global"
        self._allowed_ips: Set[str] = set(allowed_ips or [])
        self._lock = asyncio.Lock()

    async def get_mode(self) -> str:
        """Return the current network mode string."""
        async with self._lock:
            return self._mode

    async def set_mode(self, mode: str) -> None:
        """
        Update the network mode.
        Raises ValueError for unknown mode strings.
        """
        if mode not in NETWORK_MODES:
            raise ValueError(f"DSS: unknown network mode '{mode}'; must be one of {NETWORK_MODES}")
        async with self._lock:
            self._mode = mode

    async def get_allowed_ips(self) -> List[str]:
        """Return the current allowlist as a sorted list of strings."""
        async with self._lock:
            return sorted(self._allowed_ips)

    async def set_allowed_ips(self, ips: List[str]) -> None:
        """Replace the entire allowed IP/CIDR allowlist."""
        async with self._lock:
            self._allowed_ips = set(ips)

    async def add_allowed_ip(self, ip: str) -> None:
        """Add a single IP or CIDR to the allowlist."""
        async with self._lock:
            self._allowed_ips.add(ip)

    async def remove_allowed_ip(self, ip: str) -> None:
        """Remove a single IP or CIDR from the allowlist."""
        async with self._lock:
            self._allowed_ips.discard(ip)

    async def is_allowed(self, client_ip: str) -> bool:
        """
        Return True if the client_ip is permitted under the current network policy.
        - global: always True
        - lan: True only for RFC-1918 / loopback addresses
        - allowlist: True only if client_ip matches an entry or falls within a CIDR range
        """
        async with self._lock:
            mode = self._mode
            allowed = set(self._allowed_ips)

        if mode == "global":
            return True
        if mode == "lan":
            return self._is_lan_address(client_ip)
        if mode == "allowlist":
            return self._matches_allowlist(client_ip, allowed)
        return False

    def _is_lan_address(self, ip: str) -> bool:
        """Return True if ip falls within any RFC-1918 or loopback network."""
        try:
            addr = ipaddress.ip_address(ip)
            return any(addr in net for net in _LAN_NETWORKS)
        except ValueError:
            return False

    def _matches_allowlist(self, ip: str, allowed: Set[str]) -> bool:
        """Return True if ip exactly matches or is contained within an allowed CIDR entry."""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for entry in allowed:
            try:
                if "/" in entry:
                    if addr in ipaddress.ip_network(entry, strict=False):
                        return True
                elif str(addr) == entry:
                    return True
            except ValueError:
                continue
        return False
