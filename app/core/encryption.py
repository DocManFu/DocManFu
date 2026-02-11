"""Fernet symmetric encryption for secret settings (API keys, etc.)."""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Derive a Fernet key from JWT_SECRET_KEY (SHA-256 → base64-urlsafe 32 bytes)."""
    global _fernet
    if _fernet is None:
        secret = settings.JWT_SECRET_KEY
        if not secret:
            raise ValueError("JWT_SECRET_KEY must be set for encryption")
        key_bytes = hashlib.sha256(secret.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value and return the ciphertext as a UTF-8 string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns empty string on failure."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as exc:
        logger.warning("Failed to decrypt value: %s", exc)
        return ""
