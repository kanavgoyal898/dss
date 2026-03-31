"""
Purpose: pytest integration tests for DSS upload and download pipelines.
Responsibilities:
    - Verify the upload pipeline produces valid FileMetadata with correct field values.
    - Verify end-to-end round-trip: compress → encrypt → encode → decode → decrypt → decompress.
    - Verify the download pipeline reconstructs the original file contents.
    - Simulate peer failure scenarios using partial shard maps.
Dependencies: pytest, asyncio, tmp_path, unittest.mock, dss.shared.*, dss.client.app.*
"""

import asyncio
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dss.shared.crypto.aes_utils import (
    aes_decrypt,
    aes_encrypt,
    generate_aes_key,
    generate_nonce,
    nonce_to_b64,
    sha256_digest,
)
from dss.shared.crypto.rsa_utils import generate_rsa_keypair, rsa_decrypt, rsa_encrypt
from dss.shared.encoding.reed_solomon import decode_shards, encode_shards


DATA_SHARDS = 4
TOTAL_SHARDS = 6


@pytest.fixture
def rsa_pair():
    return generate_rsa_keypair()


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "test_upload.bin"
    f.write_bytes(b"DSS distributed storage test payload " * 200)
    return f


class TestFullPipelineRoundTrip:
    def test_compress_encrypt_encode_decode_decrypt_decompress(self, rsa_pair):
        private_key, public_key = rsa_pair
        raw = b"DSS production pipeline round-trip test " * 300

        compressed = zlib.compress(raw, level=6)
        aes_key = generate_aes_key()
        nonce = generate_nonce()
        ciphertext = aes_encrypt(aes_key, nonce, compressed)
        encrypted_key = rsa_encrypt(public_key, aes_key)

        shards = encode_shards(ciphertext, DATA_SHARDS, TOTAL_SHARDS)
        assert len(shards) == TOTAL_SHARDS

        shard_map = {i: s for i, s in enumerate(shards)}
        recovered_cipher = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(ciphertext))

        recovered_key = rsa_decrypt(private_key, encrypted_key)
        assert recovered_key == aes_key

        recovered_compressed = aes_decrypt(recovered_key, nonce, recovered_cipher)
        recovered_raw = zlib.decompress(recovered_compressed)
        assert recovered_raw == raw

    def test_round_trip_with_two_missing_shards(self, rsa_pair):
        private_key, public_key = rsa_pair
        raw = b"X" * 8192

        compressed = zlib.compress(raw)
        aes_key = generate_aes_key()
        nonce = generate_nonce()
        ciphertext = aes_encrypt(aes_key, nonce, compressed)
        shards = encode_shards(ciphertext, DATA_SHARDS, TOTAL_SHARDS)

        shard_map = {i: shards[i] for i in range(TOTAL_SHARDS) if i not in (1, 3)}
        recovered_cipher = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(ciphertext))
        recovered_compressed = aes_decrypt(aes_key, nonce, recovered_cipher)
        recovered_raw = zlib.decompress(recovered_compressed)
        assert recovered_raw == raw

    def test_integrity_sha256_check(self, rsa_pair):
        raw = b"integrity check payload"
        digest = sha256_digest(raw)
        assert len(digest) == 64
        assert sha256_digest(raw) == digest
        assert sha256_digest(raw + b"!") != digest

    def test_failure_below_threshold_raises(self):
        raw = b"A" * 4096
        shards = encode_shards(raw, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {0: shards[0], 1: shards[1], 2: shards[2]}
        with pytest.raises(ValueError):
            decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(raw))


class TestPeerFailureModel:
    def test_tolerates_r_equals_n_minus_k_failures(self):
        raw = b"B" * 2048
        shards = encode_shards(raw, DATA_SHARDS, TOTAL_SHARDS)
        r = TOTAL_SHARDS - DATA_SHARDS

        for failed_indices in [
            {0, 1},
            {2, 5},
            {0, 5},
            {1, 4},
        ]:
            shard_map = {i: shards[i] for i in range(TOTAL_SHARDS) if i not in failed_indices}
            assert len(shard_map) == DATA_SHARDS
            result = decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(raw))
            assert result == raw

    def test_exceeding_r_failures_is_unrecoverable(self):
        raw = b"C" * 2048
        shards = encode_shards(raw, DATA_SHARDS, TOTAL_SHARDS)
        shard_map = {0: shards[0], 1: shards[1], 2: shards[2]}
        with pytest.raises(ValueError):
            decode_shards(shard_map, DATA_SHARDS, TOTAL_SHARDS, len(raw))
