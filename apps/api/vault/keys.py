import base64
import binascii
import os
import json
from pathlib import Path

from django.conf import settings

from .crypto import VaultCryptoError
from .maintenance import _protected_file


def _decode(value: str) -> bytes:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise VaultCryptoError("Vault key material is unavailable")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VaultCryptoError("Vault key material is unavailable") from exc
    if len(decoded) != 32:
        raise VaultCryptoError("Vault key material is unavailable")
    return decoded


def _load_provider():
    configured_path = str(getattr(settings, "VAULT_KEK_PROVIDER_FILE", "") or "")
    if not configured_path:
        return None
    if os.environ.get("VAULT_KEK_BASE64", "") or str(getattr(settings, "VAULT_KEK_FILE", "") or ""):
        raise VaultCryptoError("Vault key material is unavailable")
    try:
        path = _protected_file(configured_path, setting_name="VAULT_KEK_PROVIDER_FILE")
        document = json.loads(path.read_text(encoding="utf-8"))
        if set(document) != {"schemaVersion", "activeGeneration", "generations"} or document["schemaVersion"] != 1:
            raise VaultCryptoError("Vault key material is unavailable")
        active, entries = document["activeGeneration"], document["generations"]
        if isinstance(active, bool) or not isinstance(active, int) or active <= 0 or not isinstance(entries, list):
            raise VaultCryptoError("Vault key material is unavailable")
        decoded = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"generation", "keyBase64"}:
                raise VaultCryptoError("Vault key material is unavailable")
            generation = entry["generation"]
            if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0 or generation in decoded:
                raise VaultCryptoError("Vault key material is unavailable")
            decoded[generation] = _decode(entry["keyBase64"])
        if active not in decoded:
            raise VaultCryptoError("Vault key material is unavailable")
        return active, decoded
    except VaultCryptoError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError, Exception) as exc:
        raise VaultCryptoError("Vault key material is unavailable") from exc


def active_kek_generation() -> int:
    provider = _load_provider()
    return provider[0] if provider is not None else 1


def load_kek(generation=None) -> bytes:
    """Load a base64-encoded 256-bit KEK from exactly one external boundary."""
    provider = _load_provider()
    if provider is not None:
        active, generations = provider
        requested = active if generation is None else generation
        if isinstance(requested, bool) or not isinstance(requested, int) or requested not in generations:
            raise VaultCryptoError("Vault key material is unavailable")
        return generations[requested]
    if generation not in (None, 1):
        raise VaultCryptoError("Vault key material is unavailable")
    injected = os.environ.get("VAULT_KEK_BASE64", "")
    configured_path = str(getattr(settings, "VAULT_KEK_FILE", "") or "")
    if bool(injected) == bool(configured_path):
        raise VaultCryptoError("Vault key material is unavailable")
    if injected:
        return _decode(injected)
    try:
        configured = Path(configured_path)
        if configured.is_symlink():
            raise VaultCryptoError("Vault key material is unavailable")
        path = configured.resolve(strict=True)
        repository = Path(settings.REPOSITORY_DIR).resolve(strict=True)
        if path == repository or repository in path.parents:
            raise VaultCryptoError("Vault key material is unavailable")
        if not path.is_file():
            raise VaultCryptoError("Vault key material is unavailable")
        return _decode(path.read_text(encoding="ascii"))
    except VaultCryptoError:
        raise
    except (OSError, UnicodeError) as exc:
        raise VaultCryptoError("Vault key material is unavailable") from exc
