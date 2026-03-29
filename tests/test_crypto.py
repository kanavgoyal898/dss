"""
Purpose: pytest test suite for DSS cryptographic primitives.
Responsibilities:
    - Verify AES-256-GCM encrypt/decrypt round-trip correctness.
    - Verify tampered ciphertext raises InvalidTag.
    - Verify RSA key generation, PEM serialization, and deserialization.
    - Verify RSA OAEP encrypt/decrypt round-trip.
    - Verify RSA signature sign/verify correctness.
    - Verify invalid signatures are rejected.
    - Verify SHA-256 digest determinism.
    - Verify node_id derivation is stable and consistent.
Dependencies: pytest, cryptography, dss.shared.crypto
"""

import pytest

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


class TestAES:
    def test_encrypt_decrypt_round_trip(self):
        key = generate_aes_key()
        nonce = generate_nonce()
        plaintext = b"DSS confidential payload"
        ciphertext = aes_encrypt(key, nonce, plaintext)
        assert aes_decrypt(key, nonce, ciphertext) == plaintext

    def test_different_keys_produce_different_ciphertext(self):
        nonce = generate_nonce()
        plaintext = b"DSS test"
        ct1 = aes_encrypt(generate_aes_key(), nonce, plaintext)
        ct2 = aes_encrypt(generate_aes_key(), nonce, plaintext)
        assert ct1 != ct2

    def test_tampered_ciphertext_raises(self):
        from cryptography.exceptions import InvalidTag
        key = generate_aes_key()
        nonce = generate_nonce()
        ciphertext = aes_encrypt(key, nonce, b"sensitive data")
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        with pytest.raises(InvalidTag):
            aes_decrypt(key, nonce, bytes(tampered))

    def test_wrong_nonce_raises(self):
        from cryptography.exceptions import InvalidTag
        key = generate_aes_key()
        nonce1 = generate_nonce()
        nonce2 = generate_nonce()
        ciphertext = aes_encrypt(key, nonce1, b"data")
        with pytest.raises(InvalidTag):
            aes_decrypt(key, nonce2, ciphertext)

    def test_key_b64_round_trip(self):
        key = generate_aes_key()
        assert b64_to_key(key_to_b64(key)) == key

    def test_nonce_b64_round_trip(self):
        nonce = generate_nonce()
        assert b64_to_nonce(nonce_to_b64(nonce)) == nonce

    def test_sha256_deterministic(self):
        data = b"DSS shard bytes"
        assert sha256_digest(data) == sha256_digest(data)

    def test_sha256_different_inputs(self):
        assert sha256_digest(b"abc") != sha256_digest(b"def")

    def test_generated_key_length(self):
        assert len(generate_aes_key()) == 32

    def test_generated_nonce_length(self):
        assert len(generate_nonce()) == 12


class TestRSA:
    def setup_method(self):
        self.private_key, self.public_key = generate_rsa_keypair()

    def test_pem_serialization_round_trip(self):
        priv_pem = private_key_to_pem(self.private_key)
        pub_pem = public_key_to_pem(self.public_key)
        recovered_priv = pem_to_private_key(priv_pem)
        recovered_pub = pem_to_public_key(pub_pem)
        assert private_key_to_pem(recovered_priv) == priv_pem
        assert public_key_to_pem(recovered_pub) == pub_pem

    def test_rsa_encrypt_decrypt_round_trip(self):
        secret = b"DSS AES key material 32 bytes ok"
        ciphertext_b64 = rsa_encrypt(self.public_key, secret)
        recovered = rsa_decrypt(self.private_key, ciphertext_b64)
        assert recovered == secret

    def test_rsa_encrypt_different_each_time(self):
        secret = b"same plaintext"
        ct1 = rsa_encrypt(self.public_key, secret)
        ct2 = rsa_encrypt(self.public_key, secret)
        assert ct1 != ct2

    def test_sign_and_verify(self):
        payload = b"DSS challenge message"
        sig = sign_payload(self.private_key, payload)
        assert verify_signature(self.public_key, payload, sig) is True

    def test_verify_wrong_payload_fails(self):
        payload = b"original message"
        sig = sign_payload(self.private_key, payload)
        assert verify_signature(self.public_key, b"tampered message", sig) is False

    def test_verify_wrong_key_fails(self):
        _, other_pub = generate_rsa_keypair()
        payload = b"DSS message"
        sig = sign_payload(self.private_key, payload)
        assert verify_signature(other_pub, payload, sig) is False

    def test_node_id_stable(self):
        id1 = derive_node_id(self.public_key)
        id2 = derive_node_id(self.public_key)
        assert id1 == id2
        assert len(id1) == 32

    def test_node_id_unique_per_key(self):
        _, other_pub = generate_rsa_keypair()
        assert derive_node_id(self.public_key) != derive_node_id(other_pub)
