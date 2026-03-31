"""
Purpose: pytest configuration and shared fixtures for the DSS test suite.
Responsibilities:
    - Register the asyncio pytest plugin mode.
    - Provide reusable fixtures: RSA key pairs, temp directories, sample payloads.
Dependencies: pytest, pytest-asyncio
"""

import os

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sample_payload_small():
    """Return a small deterministic byte payload for fast tests."""
    return b"DSS small payload " * 10


@pytest.fixture
def sample_payload_large():
    """Return a 1 MB random byte payload for throughput tests."""
    return os.urandom(1024 * 1024)
