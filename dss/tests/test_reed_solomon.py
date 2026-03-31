"""
Purpose: pytest test suite for DSS Reed-Solomon encoding and shard reconstruction.
Responsibilities:
    - Verify encode_shards produces the correct number of shards.
    - Verify decode_shards reconstructs the original payload from all shards.
    - Verify decode_shards tolerates up to (total - data) missing shards.
    - Verify decode_shards raises ValueError when too few shards are available.
    - Verify encode/decode round-trip for various payload sizes.
Dependencies: pytest, dss.shared.encoding.reed_solomon
"""

import os

import pytest

from dss.shared.encoding.reed_solomon import decode_shards, encode_shards


DATA_SHARDS = 4
TOTAL_SHARDS = 6
PARITY_SHARDS = TOTAL_SHARDS - DATA_SHARDS


def _random_payload(size: int) -> bytes:
    return os.urandom(size)


class TestEncodeShards:
    def test_produces_correct_shard_count(self):
        payload = _random_payload(1024)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        assert len(shards) == TOTAL_SHARDS

    def test_all_shards_same_length(self):
        payload = _random_payload(1024)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        lengths = {len(s) for s in shards}
        assert len(lengths) == 1

    def test_invalid_data_shards_raises(self):
        with pytest.raises(ValueError):
            encode_shards(b"x" * 64, 1, 6)

    def test_total_not_greater_than_data_raises(self):
        with pytest.raises(ValueError):
            encode_shards(b"x" * 64, 6, 5)

    def test_small_payload(self):
        payload = b"DSS"
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        assert len(shards) == TOTAL_SHARDS

    def test_large_payload(self):
        payload = _random_payload(5 * 1024 * 1024)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        assert len(shards) == TOTAL_SHARDS


class TestDecodeShards:
    def test_full_reconstruction(self):
        payload = _random_payload(4096)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {i: s for i, s in enumerate(shards)}
        result = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(payload))
        assert result == payload

    def test_reconstruction_with_max_erasures(self):
        payload = _random_payload(4096)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {i: shards[i] for i in range(DATA_SHARDS)}
        result = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(payload))
        assert result == payload

    def test_reconstruction_missing_first_shards(self):
        payload = _random_payload(4096)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {i: shards[i] for i in range(PARITY_SHARDS, TOTAL_SHARDS)}
        result = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(payload))
        assert result == payload

    def test_too_few_shards_raises(self):
        payload = _random_payload(4096)
        shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {0: shards[0], 1: shards[1]}
        with pytest.raises(ValueError, match="need at least"):
            decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(payload))

    def test_round_trip_various_sizes(self):
        for size in [1, 7, 100, 999, 8192, 65535]:
            payload = _random_payload(size)
            shards = encode_shards(payload, DATA_SHARDS, TOTAL_SHARDS)
            shard_map = {i: s for i, s in enumerate(shards)}
            result = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(payload))
            assert result == payload, f"Round-trip failed for size={size}"
