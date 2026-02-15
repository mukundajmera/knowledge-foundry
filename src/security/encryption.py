"""Knowledge Foundry — Credential Encryption Service.

AES-256-GCM encryption for securely storing user credentials (API tokens, session cookies).
Compliant with EU AI Act requirements for sensitive data protection.
"""

from __future__ import annotations

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class EncryptionService:
    """Handles encryption and decryption of sensitive credentials using AES-256-GCM."""

    def __init__(self, master_key: bytes | None = None) -> None:
        """Initialize encryption service with master key.
        
        Args:
            master_key: 32-byte encryption key. If None, loads from environment.
        """
        if master_key is None:
            # Load from environment or generate for development
            key_b64 = os.getenv("ENCRYPTION_KEY")
            if key_b64:
                master_key = base64.b64decode(key_b64)
            else:
                # Generate a key for development (not for production!)
                master_key = AESGCM.generate_key(bit_length=256)
        
        if len(master_key) != 32:
            raise ValueError("Master key must be 32 bytes (256 bits)")
        
        self._aesgcm = AESGCM(master_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string to base64-encoded ciphertext.
        
        Args:
            plaintext: The sensitive data to encrypt (e.g., API token, password).
        
        Returns:
            Base64-encoded string containing nonce + ciphertext.
        """
        # Generate random nonce (12 bytes recommended for GCM)
        nonce = os.urandom(12)
        
        # Encrypt the plaintext
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        
        # Combine nonce + ciphertext and encode to base64
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("ascii")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt base64-encoded ciphertext to plaintext string.
        
        Args:
            encrypted: Base64-encoded string containing nonce + ciphertext.
        
        Returns:
            Decrypted plaintext string.
        
        Raises:
            InvalidTag: If decryption fails (tampered data or wrong key).
        """
        # Decode from base64
        combined = base64.b64decode(encrypted)
        
        # Extract nonce (first 12 bytes) and ciphertext (rest)
        nonce = combined[:12]
        ciphertext = combined[12:]
        
        # Decrypt
        plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted (base64 format check).
        
        Args:
            value: String to check.
        
        Returns:
            True if value looks like base64-encoded encrypted data.
        """
        try:
            decoded = base64.b64decode(value, validate=True)
            # Encrypted data should be at least nonce (12) + some ciphertext
            return len(decoded) > 12
        except Exception:
            return False


# Singleton instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
