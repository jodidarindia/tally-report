"""
Field-level encryption for sensitive PII data using Fernet (AES-128-CBC).
Encrypts customer names, emails, phones before storage. Decrypts on read.
"""
import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_cipher = None


def _get_cipher():
    global _cipher
    if _cipher is None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            raw = os.environ.get("JWT_SECRET", "fallback_encryption_key_change_me")
            key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        else:
            if isinstance(key, str):
                key = key.encode()
        _cipher = Fernet(key)
    return _cipher


def encrypt_field(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    try:
        return _get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return value


def decrypt_field(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    try:
        return _get_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value


def encrypt_pii(doc: dict, fields: list) -> dict:
    """Encrypt specified fields in a document."""
    encrypted = dict(doc)
    for field in fields:
        if field in encrypted and encrypted[field]:
            encrypted[field] = encrypt_field(str(encrypted[field]))
    return encrypted


def decrypt_pii(doc: dict, fields: list) -> dict:
    """Decrypt specified fields in a document."""
    decrypted = dict(doc)
    for field in fields:
        if field in decrypted and decrypted[field]:
            decrypted[field] = decrypt_field(str(decrypted[field]))
    return decrypted


PROSPECT_PII_FIELDS = ["contact_person", "email", "phone", "company_name", "gst_number", "address"]
