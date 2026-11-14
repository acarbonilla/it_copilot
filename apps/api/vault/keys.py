import base64
import binascii
import os
from pathlib import Path

from django.conf import settings

from .crypto import VaultCryptoError


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


def load_kek() -> bytes:
    """Load a base64-encoded 256-bit KEK from exactly one external boundary."""
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
