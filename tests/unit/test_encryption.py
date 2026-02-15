"""Unit tests for credential encryption service."""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from src.security.encryption import EncryptionService


class TestEncryptionService:
    """Tests for EncryptionService."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted data can be decrypted back to original."""
        service = EncryptionService()
        
        plaintext = "my-secret-api-token-12345"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypted_format_is_base64(self):
        """Test that encrypted output is valid base64."""
        service = EncryptionService()
        
        encrypted = service.encrypt("test")
        
        # Should be base64 (alphanumeric + / + =)
        assert encrypted.replace("+", "").replace("/", "").replace("=", "").isalnum()

    def test_different_encryptions_produce_different_output(self):
        """Test that same plaintext produces different ciphertext (due to random nonce)."""
        service = EncryptionService()
        
        plaintext = "test-secret"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)
        
        # Different ciphertexts due to different nonces
        assert encrypted1 != encrypted2
        
        # But both decrypt to same plaintext
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key raises error."""
        service1 = EncryptionService()
        service2 = EncryptionService()  # Different key
        
        encrypted = service1.encrypt("secret")
        
        with pytest.raises(InvalidTag):
            service2.decrypt(encrypted)

    def test_tampered_data_fails_decryption(self):
        """Test that tampered ciphertext fails decryption."""
        service = EncryptionService()
        
        encrypted = service.encrypt("test")
        
        # Tamper with the encrypted data
        tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
        
        with pytest.raises(Exception):  # Could be InvalidTag or base64 decode error
            service.decrypt(tampered)

    def test_is_encrypted_detects_encrypted_data(self):
        """Test that is_encrypted correctly identifies encrypted data."""
        service = EncryptionService()
        
        encrypted = service.encrypt("test")
        
        assert service.is_encrypted(encrypted) is True
        assert service.is_encrypted("plain-text") is False
        assert service.is_encrypted("") is False

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        service = EncryptionService()
        
        encrypted = service.encrypt("")
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == ""

    def test_encrypt_long_string(self):
        """Test encrypting long string."""
        service = EncryptionService()
        
        plaintext = "x" * 10000
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypt_unicode(self):
        """Test encrypting Unicode characters."""
        service = EncryptionService()
        
        plaintext = "Hello 世界 🌍 émojis"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext
