"""
Purpose: RSA-2048 key generation, serialization, signing, and verification for DSS peer identity.
Responsibilities:
    - Generate RSA-2048 key pairs for new peer nodes.
    - Serialize/deserialize keys to and from PEM format.
    - Sign arbitrary byte payloads with a private key.
    - Verify signatures against a public key.
    - Derive a stable node_id fingerprint from a public key.
Dependencies: cryptography
"""

import hashlib
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def generate_rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate a new RSA-2048 private/public key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def private_key_to_pem(private_key: rsa.RSAPrivateKey) -> str:
    """Serialize a private key to a PEM-encoded string."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def public_key_to_pem(public_key: rsa.RSAPublicKey) -> str:
    """Serialize a public key to a PEM-encoded string."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def pem_to_private_key(pem: str) -> rsa.RSAPrivateKey:
    """Deserialize a private key from a PEM-encoded string."""
    return serialization.load_pem_private_key(pem.encode(), password=None)


def pem_to_public_key(pem: str) -> rsa.RSAPublicKey:
    """Deserialize a public key from a PEM-encoded string."""
    return serialization.load_pem_public_key(pem.encode())


def derive_node_id(public_key: rsa.RSAPublicKey) -> str:
    """
    Derive a stable, collision-resistant node identifier from a public key.
    Returns the first 32 hex characters of the SHA-256 digest of the DER-encoded key.
    """
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der_bytes).hexdigest()[:32]


def sign_payload(private_key: rsa.RSAPrivateKey, payload: bytes) -> str:
    """
    Sign a byte payload with PKCS1v15 and SHA-256.
    Returns a base64-encoded signature string.
    """
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    return b64encode(signature).decode()


def verify_signature(public_key: rsa.RSAPublicKey, payload: bytes, signature_b64: str) -> bool:
    """
    Verify a base64-encoded PKCS1v15/SHA-256 signature against a payload.
    Returns True if valid, False otherwise.
    """
    try:
        public_key.verify(b64decode(signature_b64), payload, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def rsa_encrypt(public_key: rsa.RSAPublicKey, plaintext: bytes) -> str:
    """
    Encrypt plaintext bytes with RSA-OAEP/SHA-256.
    Returns a base64-encoded ciphertext string.
    """
    ciphertext = public_key.encrypt(
        plaintext,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return b64encode(ciphertext).decode()


def rsa_decrypt(private_key: rsa.RSAPrivateKey, ciphertext_b64: str) -> bytes:
    """
    Decrypt a base64-encoded RSA-OAEP/SHA-256 ciphertext.
    Returns the original plaintext bytes.
    """
    return private_key.decrypt(
        b64decode(ciphertext_b64),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
