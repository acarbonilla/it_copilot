import json
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import ENVELOPE_SCHEMA_VERSION, ENVELOPE_VERSION, NONCE_BYTES, TAG_BYTES


class VaultCryptoError(Exception):
    """Secret-free failure at the vault cryptographic boundary."""


@dataclass(frozen=True)
class EncryptionContext:
    owner_id: int
    record_id: str
    credential_type: str
    schema_version: int = ENVELOPE_SCHEMA_VERSION


@dataclass(frozen=True)
class EncryptionEnvelope:
    envelope_version: int
    schema_version: int
    key_version: int
    nonce: bytes
    ciphertext: bytes
    tag: bytes


@dataclass(frozen=True)
class WrappedKeyEnvelope:
    envelope_version: int
    key_version: int
    nonce: bytes
    wrapped_dek: bytes
    tag: bytes


def _aad(context: EncryptionContext) -> bytes:
    if (
        isinstance(context.owner_id, bool)
        or not isinstance(context.owner_id, int)
        or context.owner_id <= 0
        or not isinstance(context.record_id, str)
        or not context.record_id
        or not isinstance(context.credential_type, str)
        or not context.credential_type
        or context.schema_version != ENVELOPE_SCHEMA_VERSION
    ):
        raise VaultCryptoError("Vault encryption context is invalid")
    return json.dumps(
        {
            "context": "it-copilot/vault-record",
            "credential_type": context.credential_type,
            "owner_id": context.owner_id,
            "record_id": context.record_id,
            "schema_version": context.schema_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _key_aad(*, owner_id: int, key_version: int) -> bytes:
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id <= 0:
        raise VaultCryptoError("Vault key context is invalid")
    if isinstance(key_version, bool) or not isinstance(key_version, int) or key_version <= 0:
        raise VaultCryptoError("Vault key context is invalid")
    return json.dumps(
        {"context": "it-copilot/vault-owner-key", "key_version": key_version, "owner_id": owner_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != 32:
        raise VaultCryptoError("Vault key material is unavailable")
    return key


def validate_envelope(envelope: EncryptionEnvelope) -> None:
    if (
        not isinstance(envelope, EncryptionEnvelope)
        or envelope.envelope_version != ENVELOPE_VERSION
        or envelope.schema_version != ENVELOPE_SCHEMA_VERSION
        or isinstance(envelope.key_version, bool)
        or not isinstance(envelope.key_version, int)
        or envelope.key_version <= 0
        or not isinstance(envelope.nonce, bytes)
        or len(envelope.nonce) != NONCE_BYTES
        or not isinstance(envelope.ciphertext, bytes)
        or not envelope.ciphertext
        or not isinstance(envelope.tag, bytes)
        or len(envelope.tag) != TAG_BYTES
    ):
        raise VaultCryptoError("Vault envelope is invalid")


def encrypt(*, dek: bytes, plaintext: bytes, context: EncryptionContext, key_version: int) -> EncryptionEnvelope:
    _validate_key(dek)
    if not isinstance(plaintext, bytes) or not plaintext:
        raise VaultCryptoError("Vault plaintext is invalid")
    if isinstance(key_version, bool) or not isinstance(key_version, int) or key_version <= 0:
        raise VaultCryptoError("Vault key version is invalid")
    try:
        nonce = os.urandom(NONCE_BYTES)
        combined = AESGCM(dek).encrypt(nonce, plaintext, _aad(context))
    except VaultCryptoError:
        raise
    except Exception as exc:
        raise VaultCryptoError("Vault encryption failed") from exc
    return EncryptionEnvelope(
        envelope_version=ENVELOPE_VERSION,
        schema_version=ENVELOPE_SCHEMA_VERSION,
        key_version=key_version,
        nonce=nonce,
        ciphertext=combined[:-TAG_BYTES],
        tag=combined[-TAG_BYTES:],
    )


def decrypt(*, dek: bytes, envelope: EncryptionEnvelope, context: EncryptionContext) -> bytes:
    _validate_key(dek)
    validate_envelope(envelope)
    try:
        return AESGCM(dek).decrypt(envelope.nonce, envelope.ciphertext + envelope.tag, _aad(context))
    except (InvalidTag, ValueError, TypeError) as exc:
        raise VaultCryptoError("Vault decryption failed") from exc
    except Exception as exc:
        raise VaultCryptoError("Vault decryption failed") from exc


def wrap_dek(*, kek: bytes, dek: bytes, owner_id: int, key_version: int) -> WrappedKeyEnvelope:
    _validate_key(kek)
    _validate_key(dek)
    try:
        nonce = os.urandom(NONCE_BYTES)
        combined = AESGCM(kek).encrypt(nonce, dek, _key_aad(owner_id=owner_id, key_version=key_version))
    except VaultCryptoError:
        raise
    except Exception as exc:
        raise VaultCryptoError("Vault key wrapping failed") from exc
    return WrappedKeyEnvelope(ENVELOPE_VERSION, key_version, nonce, combined[:-TAG_BYTES], combined[-TAG_BYTES:])


def unwrap_dek(*, kek: bytes, envelope: WrappedKeyEnvelope, owner_id: int) -> bytes:
    _validate_key(kek)
    if (
        not isinstance(envelope, WrappedKeyEnvelope)
        or envelope.envelope_version != ENVELOPE_VERSION
        or not isinstance(envelope.key_version, int)
        or envelope.key_version <= 0
        or not isinstance(envelope.nonce, bytes)
        or len(envelope.nonce) != NONCE_BYTES
        or not isinstance(envelope.wrapped_dek, bytes)
        or len(envelope.wrapped_dek) != 32
        or not isinstance(envelope.tag, bytes)
        or len(envelope.tag) != TAG_BYTES
    ):
        raise VaultCryptoError("Vault wrapped key is invalid")
    try:
        return AESGCM(kek).decrypt(
            envelope.nonce,
            envelope.wrapped_dek + envelope.tag,
            _key_aad(owner_id=owner_id, key_version=envelope.key_version),
        )
    except (InvalidTag, ValueError, TypeError) as exc:
        raise VaultCryptoError("Vault key unwrapping failed") from exc
    except Exception as exc:
        raise VaultCryptoError("Vault key unwrapping failed") from exc
