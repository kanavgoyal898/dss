"""
Purpose: Reed-Solomon erasure coding for DSS shard generation and reconstruction.
Responsibilities:
    - Encode a data payload into k data shards + (n-k) parity shards using zfec.
    - Reconstruct the original payload from any k of n available shards.
    - Validate shard count parameters to ensure r = n - k failure tolerance is met.
Dependencies: zfec
"""

from __future__ import annotations

from typing import Dict, List, Optional

import zfec


def encode_shards(data: bytes, data_shards: int, total_shards: int) -> List[bytes]:
    """
    Encode raw data bytes into total_shards shards using Reed-Solomon
    (data_shards, total_shards).

    The first data_shards shards hold the original data bytes (systematic).
    The remaining (total_shards - data_shards) shards are parity shards.

    Pads data to a multiple of data_shards bytes before encoding.

    Raises ValueError if parameters violate RS constraints (k < 2, n <= k, n > 256).
    """
    if data_shards < 2:
        raise ValueError("DSS: data_shards must be >= 2")
    if total_shards <= data_shards:
        raise ValueError("DSS: total_shards must be > data_shards")
    if total_shards > 256:
        raise ValueError("DSS: total_shards exceeds zfec capacity (max 256)")

    padding_len = (data_shards - len(data) % data_shards) % data_shards
    padded = data + b"\x00" * padding_len
    shard_size = len(padded) // data_shards

    chunks = [padded[i * shard_size : (i + 1) * shard_size] for i in range(data_shards)]
    encoder = zfec.Encoder(data_shards, total_shards)
    return list(encoder.encode(chunks))


def decode_shards(
    shards: Dict[int, bytes],
    data_shards: int,
    total_shards: int,
    original_size: Optional[int],
) -> bytes:
    """
    Reconstruct original data from any data_shards of total_shards available shards.

    shards is a dict mapping shard_index -> shard_bytes; missing indices are treated
    as erasures. Raises ValueError if fewer than data_shards shards are provided.

    Returns the original byte sequence trimmed to original_size (if provided).
    """
    if len(shards) < data_shards:
        raise ValueError(
            f"DSS: need at least {data_shards} shards for reconstruction, "
            f"got {len(shards)}"
        )

    available_indices = sorted(shards.keys())[:data_shards]
    chunks = [shards[i] for i in available_indices]

    decoder = zfec.Decoder(data_shards, total_shards)
    recovered = decoder.decode(chunks, available_indices)

    raw = b"".join(recovered)
    return raw[:original_size] if original_size is not None else raw