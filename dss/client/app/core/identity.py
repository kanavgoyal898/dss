"""
Purpose: DSS Peer Node identity management — RSA key pair persistence and node_id derivation.
Responsibilities:
    - Generate and persist an RSA-2048 key pair to disk on first launch.
    - Load an existing key pair from the identity directory.
    - Derive the stable node_id fingerprint from the public key.
    - Provide the identity as a singleton accessible to all client services.
Dependencies: pathlib, dss.shared.crypto.rsa_utils, dss.client.app.core.config
"""

import logging
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from dss.shared.crypto.rsa_utils import (
    derive_node_id,
    generate_rsa_keypair,
    pem_to_private_key,
    pem_to_public_key,
    private_key_to_pem,
    public_key_to_pem,
)

logger = logging.getLogger("dss.identity")

_PRIVATE_KEY_FILE = "private_key.pem"
_PUBLIC_KEY_FILE = "public_key.pem"
_NODE_ID_FILE = "node_id.txt"


class NodeIdentity:
    """Encapsulates the cryptographic identity of a DSS peer node."""

    def __init__(
        self,
        node_id: str,
        private_key: RSAPrivateKey,
        public_key: RSAPublicKey,
        public_key_pem: str,
    ) -> None:
        """Store the identity components; not constructed directly — use load_or_create."""
        self.node_id = node_id
        self.private_key = private_key
        self.public_key = public_key
        self.public_key_pem = public_key_pem


def load_or_create_identity(identity_dir: Path) -> NodeIdentity:
    """
    Load an existing RSA identity from identity_dir, or generate and persist a new one.
    Returns a NodeIdentity instance with all components populated.
    """
    identity_dir.mkdir(parents=True, exist_ok=True)
    priv_path = identity_dir / _PRIVATE_KEY_FILE
    pub_path = identity_dir / _PUBLIC_KEY_FILE

    if priv_path.exists() and pub_path.exists():
        private_key = pem_to_private_key(priv_path.read_text())
        public_key = pem_to_public_key(pub_path.read_text())
        logger.info("DSS identity loaded from %s", identity_dir)
    else:
        private_key, public_key = generate_rsa_keypair()
        priv_path.write_text(private_key_to_pem(private_key))
        pub_path.write_text(public_key_to_pem(public_key))
        logger.info("DSS identity generated and saved to %s", identity_dir)

    public_key_pem = public_key_to_pem(public_key)
    node_id = derive_node_id(public_key)
    return NodeIdentity(
        node_id=node_id,
        private_key=private_key,
        public_key=public_key,
        public_key_pem=public_key_pem,
    )
