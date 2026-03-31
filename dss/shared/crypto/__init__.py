"""
Purpose: Public re-exports for dss.shared.crypto package.
Responsibilities: Expose cryptographic primitives from a single import point.
Dependencies: dss.shared.crypto.rsa_utils, dss.shared.crypto.aes_utils
"""

from dss.shared.crypto.aes_utils import (
    aes_decrypt,
    aes_encrypt,
    b64_to_key,
    b64_to_nonce,
    generate_aes_key,
    generate_nonce,
    key_to_b64,
    nonce_to_b64,
    sha256_digest,
)
from dss.shared.crypto.rsa_utils import (
    derive_node_id,
    generate_rsa_keypair,
    pem_to_private_key,
    pem_to_public_key,
    private_key_to_pem,
    public_key_to_pem,
    rsa_decrypt,
    rsa_encrypt,
    sign_payload,
    verify_signature,
)

__all__ = [
    "generate_rsa_keypair",
    "private_key_to_pem",
    "public_key_to_pem",
    "pem_to_private_key",
    "pem_to_public_key",
    "derive_node_id",
    "sign_payload",
    "verify_signature",
    "rsa_encrypt",
    "rsa_decrypt",
    "generate_aes_key",
    "generate_nonce",
    "aes_encrypt",
    "aes_decrypt",
    "sha256_digest",
    "key_to_b64",
    "b64_to_key",
    "nonce_to_b64",
    "b64_to_nonce",
]
