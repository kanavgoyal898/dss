"""
Purpose: pytest test suite for DSS local shard storage.
Responsibilities:
    - Verify write and read round-trip correctness.
    - Verify integrity verification passes for intact shards.
    - Verify integrity verification fails for tampered shard bytes.
    - Verify deletion removes shard and metadata files.
    - Verify list_shards returns correct metadata.
    - Verify total_used_bytes reflects stored data.
Dependencies: pytest, tmp_path, dss.client.app.storage.shard_store
"""

import hashlib

import pytest

from dss.client.app.storage.shard_store import ShardStore


@pytest.fixture
def store(tmp_path):
    return ShardStore(tmp_path / "shards")


class TestShardStore:
    def test_write_and_read(self, store):
        data = b"DSS shard payload data"
        sha = hashlib.sha256(data).hexdigest()
        store.write_shard("shard-001", data, sha)
        assert store.read_shard("shard-001") == data

    def test_read_missing_returns_none(self, store):
        assert store.read_shard("nonexistent-shard") is None

    def test_verify_passes_intact_shard(self, store):
        data = b"intact shard bytes"
        sha = hashlib.sha256(data).hexdigest()
        store.write_shard("shard-002", data, sha)
        assert store.verify_shard("shard-002") is True

    def test_verify_fails_tampered_shard(self, store, tmp_path):
        data = b"original shard bytes"
        sha = hashlib.sha256(data).hexdigest()
        store.write_shard("shard-003", data, sha)
        shard_path = store._shard_path("shard-003")
        shard_path.write_bytes(b"tampered content")
        assert store.verify_shard("shard-003") is False

    def test_verify_missing_shard_returns_false(self, store):
        assert store.verify_shard("does-not-exist") is False

    def test_delete_removes_shard(self, store):
        data = b"to be deleted"
        sha = hashlib.sha256(data).hexdigest()
        store.write_shard("shard-004", data, sha)
        assert store.delete_shard("shard-004") is True
        assert store.read_shard("shard-004") is None

    def test_delete_missing_returns_false(self, store):
        assert store.delete_shard("ghost-shard") is False

    def test_list_shards_returns_metadata(self, store):
        data = b"listed shard"
        sha = hashlib.sha256(data).hexdigest()
        store.write_shard("shard-005", data, sha)
        listing = store.list_shards()
        ids = [item["shard_id"] for item in listing]
        assert "shard-005" in ids

    def test_total_used_bytes(self, store):
        data1 = b"a" * 512
        data2 = b"b" * 256
        store.write_shard("shard-006", data1, hashlib.sha256(data1).hexdigest())
        store.write_shard("shard-007", data2, hashlib.sha256(data2).hexdigest())
        assert store.total_used_bytes() == 768

    def test_multiple_write_list(self, store):
        for i in range(5):
            d = f"shard data {i}".encode()
            store.write_shard(f"shard-{i:03d}", d, hashlib.sha256(d).hexdigest())
        assert len(store.list_shards()) == 5
