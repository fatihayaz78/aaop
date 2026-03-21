"""Fernet-based encryption utilities for secret storage."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def get_fernet(secret_key: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())
    return Fernet(key)


def encrypt(value: str, secret_key: str) -> str:
    return get_fernet(secret_key).encrypt(value.encode()).decode()


def decrypt(value: str, secret_key: str) -> str:
    return get_fernet(secret_key).decrypt(value.encode()).decode()
