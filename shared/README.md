# DSS Shared

## Purpose

Cross-cutting library code used by both the Coordinator and Peer Node. Contains all cryptographic primitives, the Reed-Solomon erasure coding engine, and the shared Pydantic schemas that define the API contract.

## Modules

```
shared/
├── crypto/
│   ├── rsa_utils.py    # RSA-2048 keygen, PEM I/O, OAEP encrypt/decrypt, sign/verify
│   └── aes_utils.py    # AES-256-GCM encrypt/decrypt, nonce/key generation, SHA-256
└── encoding/
│   └── reed_solomon.py # Pure-Python GF(2^8) RS encoder + Lagrange interpolation decoder
└── schemas/
    ├── peer.py         # PeerRegistration, PeerInfo, HeartbeatRequest/Response
    ├── shard.py        # ShardInfo, ShardLocation, ShardVerification
    └── file.py         # FileUploadInit/Complete, FileMetadata, FileDownloadResponse
```

## Reed-Solomon

The RS implementation uses a **systematic code** — the first `k` shards contain the original data unmodified. Parity shards are computed by evaluating the Lagrange interpolating polynomial at extra evaluation points in GF(2^8).

```python
shards = encode_shards(data, data_shards=4, total_shards=6)
recovered = decode_shards({0: s0, 2: s2, 4: s4, 5: s5}, 4, 6, original_size=len(data))
```

Any 4 of 6 shards are sufficient to reconstruct — tolerates 2 simultaneous node failures.

## Cryptography Summary

```
RSA-2048 (per node)      key generation, OAEP encrypt/decrypt, PKCS1v15 sign/verify
AES-256-GCM (per file)   symmetric encryption; key wrapped with owner RSA public key
SHA-256 (per shard)      integrity verification before assembly
```

## Troubleshooting

**`ValueError: need at least k shards`** — Reed-Solomon received fewer shards than the data_shards threshold. More peer nodes need to be online.

**`cryptography.exceptions.InvalidTag`** — AES-GCM authentication failed. The shard data was corrupted or the wrong key/nonce was used.
