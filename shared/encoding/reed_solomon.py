"""
Purpose: Reed-Solomon erasure coding for DSS shard generation and reconstruction.
Responsibilities:
    - Encode a data payload into k data shards + (n-k) parity shards using GF(2^8) arithmetic.
    - Reconstruct the original payload from any k of n available shards via Lagrange interpolation.
    - Provide a pure-Python Galois Field GF(2^8) implementation.
    - Validate shard count parameters to ensure r = n - k failure tolerance is met.
Dependencies: None (pure Python)
"""

from __future__ import annotations

from typing import Dict, List, Optional


_GF_EXP: List[int] = [0] * 512
_GF_LOG: List[int] = [0] * 256


def _build_gf_tables() -> None:
    """Pre-compute GF(2^8) exponent and log tables using primitive polynomial 0x11d."""
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_build_gf_tables()


def _gf_mul(a: int, b: int) -> int:
    """Multiply two GF(2^8) elements."""
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] + _GF_LOG[b]) % 255]


def _gf_div(a: int, b: int) -> int:
    """Divide two GF(2^8) elements. Raises ZeroDivisionError for b=0."""
    if b == 0:
        raise ZeroDivisionError("GF division by zero")
    if a == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] - _GF_LOG[b] + 255) % 255]


def _lagrange_eval(xs: List[int], ys: List[int], eval_x: int) -> int:
    """
    Evaluate the unique polynomial of degree < len(xs) that passes through all
    (xs[i], ys[i]) points, at the point eval_x, using Lagrange interpolation in GF(2^8).
    In GF(2^8) addition and subtraction are both XOR.
    """
    k = len(xs)
    result = 0
    for i in range(k):
        numerator = 1
        denominator = 1
        for j in range(k):
            if j == i:
                continue
            numerator = _gf_mul(numerator, xs[j] ^ eval_x)
            denominator = _gf_mul(denominator, xs[i] ^ xs[j])
        result ^= _gf_mul(ys[i], _gf_div(numerator, denominator))
    return result


def _build_eval_points(n: int) -> List[int]:
    """
    Return n distinct non-zero evaluation points in GF(2^8).
    Uses 1, 2, 3, ..., n (valid for n <= 255).
    """
    if n > 255:
        raise ValueError(f"DSS: n={n} exceeds GF(2^8) capacity (max 255)")
    return list(range(1, n + 1))


def encode_shards(data: bytes, data_shards: int, total_shards: int) -> List[bytes]:
    """
    Encode raw data bytes into total_shards shards using Reed-Solomon (data_shards, total_shards).

    The first data_shards shards hold the original data bytes (systematic).
    The remaining (total_shards - data_shards) shards are parity shards computed via
    Lagrange interpolation in GF(2^8).

    Pads data to a multiple of data_shards, distributes across data shards, then
    computes parity shards by evaluating the interpolating polynomial at parity points.

    Raises ValueError if parameters violate RS constraints (n > 255, k < 2, n <= k).
    """
    if data_shards < 2:
        raise ValueError("DSS: data_shards must be >= 2")
    if total_shards <= data_shards:
        raise ValueError("DSS: total_shards must be > data_shards")
    if total_shards > 255:
        raise ValueError("DSS: total_shards exceeds GF(2^8) capacity (max 255)")

    nsym = total_shards - data_shards
    eval_points = _build_eval_points(total_shards)
    data_points = eval_points[:data_shards]
    parity_points = eval_points[data_shards:]

    padding_len = (data_shards - len(data) % data_shards) % data_shards
    padded = data + b"\x00" * padding_len
    shard_size = len(padded) // data_shards

    data_shard_list: List[List[int]] = [
        list(padded[i * shard_size:(i + 1) * shard_size])
        for i in range(data_shards)
    ]

    parity_shard_list: List[List[int]] = [[0] * shard_size for _ in range(nsym)]

    for byte_idx in range(shard_size):
        ys = [data_shard_list[i][byte_idx] for i in range(data_shards)]
        for p_idx, p_x in enumerate(parity_points):
            parity_shard_list[p_idx][byte_idx] = _lagrange_eval(data_points, ys, p_x)

    return [bytes(s) for s in data_shard_list] + [bytes(s) for s in parity_shard_list]


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

    Uses Lagrange interpolation in GF(2^8) to recover each data shard byte-by-byte
    from the available shard values at their evaluation points.

    Returns the original byte sequence trimmed to original_size (if provided).
    """
    if len(shards) < data_shards:
        raise ValueError(
            f"DSS: need at least {data_shards} shards for reconstruction, got {len(shards)}"
        )

    eval_points = _build_eval_points(total_shards)
    available_indices = sorted(shards.keys())[:data_shards]
    avail_xs = [eval_points[i] for i in available_indices]
    data_xs = eval_points[:data_shards]

    shard_size = len(shards[available_indices[0]])
    reconstructed: List[List[int]] = [[0] * shard_size for _ in range(data_shards)]

    for byte_idx in range(shard_size):
        avail_ys = [shards[i][byte_idx] for i in available_indices]
        for d_idx, d_x in enumerate(data_xs):
            if d_idx in set(available_indices):
                reconstructed[d_idx][byte_idx] = shards[d_idx][byte_idx]
            else:
                reconstructed[d_idx][byte_idx] = _lagrange_eval(avail_xs, avail_ys, d_x)

    result: List[int] = []
    for shard in reconstructed:
        result.extend(shard)

    raw = bytes(result)
    return raw[:original_size] if original_size is not None else raw
