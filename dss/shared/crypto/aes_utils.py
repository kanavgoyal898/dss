"""
Purpose: AES-256-GCM symmetric encryption and decryption for DSS file payloads.
Responsibilities:
    - Generate cryptographically secure AES-256 keys and GCM nonces.
    - Encrypt arbitrary byte streams with AES-256-GCM, producing ciphertext + auth tag.
    - Decrypt and authenticate AES-256-GCM ciphertext, raising on tag mismatch.
    - Compute SHA-256 digests for shard integrity verification.
Dependencies: cryptography, hashlib
"""

import hashlib
import os
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_AES_KEY_BYTES = 32
_GCM_NONCE_BYTES = 12


def generate_aes_key() -> bytes:
    """Generate a 256-bit (32-byte) cryptographically secure AES key."""
    return os.urandom(_AES_KEY_BYTES)


def generate_nonce() -> bytes:
    """Generate a 96-bit (12-byte) GCM nonce."""
    return os.urandom(_GCM_NONCE_BYTES)


def aes_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext with AES-256-GCM using the given key and nonce.
    Returns ciphertext bytes with the GCM authentication tag appended.
    """
    aesgcm = AESGCM(key)
    return aesgcm.encrypt(nonce, plaintext, None)


def aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """
    Decrypt and authenticate AES-256-GCM ciphertext.
    Raises cryptography.exceptions.InvalidTag if authentication fails.
    """
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def sha256_digest(data: bytes) -> str:
    """Compute the hex-encoded SHA-256 digest of a byte sequence."""
    return hashlib.sha256(data).hexdigest()


def key_to_b64(key: bytes) -> str:
    """Encode raw key bytes as a base64 string."""
    return b64encode(key).decode()


def b64_to_key(b64: str) -> bytes:
    """Decode a base64 string back to raw key bytes."""
    return b64decode(b64)


def nonce_to_b64(nonce: bytes) -> str:
    """Encode raw nonce bytes as a base64 string."""
    return b64encode(nonce).decode()


def b64_to_nonce(b64: str) -> bytes:
    """Decode a base64 string back to raw nonce bytes."""
    return b64decode(b64)
