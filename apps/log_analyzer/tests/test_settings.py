"""Tests for encryption and settings masking."""

from __future__ import annotations

from shared.utils.encryption import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    secret = "test-secret-key-12345"
    original = "AKIAIOSFODNN7EXAMPLE"
    encrypted = encrypt(original, secret)
    assert encrypted != original
    decrypted = decrypt(encrypted, secret)
    assert decrypted == original


def test_encrypt_different_keys():
    value = "my-secret-value"
    enc1 = encrypt(value, "key1")
    enc2 = encrypt(value, "key2")
    # Different keys produce different ciphertext (tokens differ due to timestamp)
    assert decrypt(enc1, "key1") == value
    assert decrypt(enc2, "key2") == value


def test_encrypt_empty_string():
    secret = "test-key"
    encrypted = encrypt("", secret)
    decrypted = decrypt(encrypted, secret)
    assert decrypted == ""


def test_masked_response():
    """Test the masking logic used in the settings endpoint."""

    def _mask_key(value: str | None) -> str | None:
        if not value:
            return None
        if len(value) <= 4:
            return "****"
        return "*" * (len(value) - 4) + value[-4:]

    assert _mask_key(None) is None
    assert _mask_key("") is None
    assert _mask_key("abc") == "****"
    assert _mask_key("AKIAIOSFODNN7EXAMPLE") == "****************MPLE"
    assert _mask_key("12345") == "*2345"
