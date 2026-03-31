"""
Purpose: Public re-exports for dss.shared.encoding package.
Responsibilities: Expose Reed-Solomon encode/decode from a single import point.
Dependencies: dss.shared.encoding.reed_solomon
"""

from dss.shared.encoding.reed_solomon import decode_shards, encode_shards

__all__ = ["encode_shards", "decode_shards"]
