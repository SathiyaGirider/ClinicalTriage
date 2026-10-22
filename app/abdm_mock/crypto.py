"""
Simulated secure transfer pattern for ABDM-style FHIR document bundles.
Demonstrates ECDH key agreement + AES-GCM encryption + ECDSA signature.
SIMULATION ONLY. Demo keys generated per facility/doctor.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

# Cache demo doctor/facility EC key pairs in memory for simulation
_DEMO_PRIVATE_KEYS: dict[int, ec.EllipticCurvePrivateKey] = {}


def get_doctor_keypair(doctor_id: int) -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    if doctor_id not in _DEMO_PRIVATE_KEYS:
        # Standard NIST P-256 (secp256r1)
        _DEMO_PRIVATE_KEYS[doctor_id] = ec.generate_private_key(ec.SECP256R1())
    priv = _DEMO_PRIVATE_KEYS[doctor_id]
    return priv, priv.public_key()


def public_key_pem(pub: ec.EllipticCurvePublicKey) -> str:
    return pub.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def encrypt_and_sign_bundle(
    bundle_dict: dict[str, Any],
    sender_doctor_id: int,
    recipient_doctor_id: int,
) -> dict[str, Any]:
    """
    Encrypts FHIR bundle for the recipient doctor using ECDH + AES-GCM,
    and signs the ciphertext using sender's private key.
    """
    sender_priv, sender_pub = get_doctor_keypair(sender_doctor_id)
    _, recipient_pub = get_doctor_keypair(recipient_doctor_id)

    # 1. Ephemeral sender key or sender key ECDH agreement with recipient public key
    shared_key = sender_priv.exchange(ec.ECDH(), recipient_pub)

    # 2. Derive 256-bit AES key via HKDF
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"abdm-simulated-salt-demo",
        info=b"abdm-fhir-transfer",
    ).derive(shared_key)

    # 3. Encrypt payload with AES-GCM
    plaintext = json.dumps(bundle_dict).encode("utf-8")
    aesgcm = AESGCM(derived_key)
    # Generate 12-byte random nonce
    import secrets
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # 4. Sign the ciphertext with sender's ECDSA private key
    signature = sender_priv.sign(ciphertext, ec.ECDSA(hashes.SHA256()))

    return {
        "is_simulation": True,
        "notice": "ABDM simulated encrypted data transfer. Not connected to ABDM.",
        "encryption_algorithm": "ECDH-NIST-P256 + AES256-GCM",
        "signature_algorithm": "ECDSA-SHA256",
        "sender_public_key": public_key_pem(sender_pub),
        "nonce_b64": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("utf-8"),
        "signature_b64": base64.b64encode(signature).decode("utf-8"),
    }


def verify_and_decrypt_bundle(
    encrypted_payload: dict[str, Any],
    sender_doctor_id: int,
    recipient_doctor_id: int,
) -> dict[str, Any]:
    """
    Verifies ECDSA signature and decrypts the FHIR bundle.
    """
    sender_priv, sender_pub = get_doctor_keypair(sender_doctor_id)
    recipient_priv, _ = get_doctor_keypair(recipient_doctor_id)

    ciphertext = base64.b64decode(encrypted_payload["ciphertext_b64"])
    nonce = base64.b64decode(encrypted_payload["nonce_b64"])
    signature = base64.b64decode(encrypted_payload["signature_b64"])

    # 1. Verify signature
    sender_pub.verify(signature, ciphertext, ec.ECDSA(hashes.SHA256()))

    # 2. Derive shared key
    shared_key = recipient_priv.exchange(ec.ECDH(), sender_pub)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"abdm-simulated-salt-demo",
        info=b"abdm-fhir-transfer",
    ).derive(shared_key)

    # 3. Decrypt
    aesgcm = AESGCM(derived_key)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_bytes.decode("utf-8"))
