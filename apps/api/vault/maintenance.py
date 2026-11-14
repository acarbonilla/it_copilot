import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied


SCHEMA_VERSION = 1
CAPABILITIES = frozenset({
    "credential.purge",
    "credential.hold.create",
    "credential.hold.release",
    "key.rotate.kek",
    "key.rotate.dek",
    "backup.create",
    "recovery.verify",
    "key.retire.online",
})
_OPERATOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", re.ASCII)
_HEX_64 = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


class MaintenanceAuthorizationDenied(PermissionDenied):
    pass


@dataclass(frozen=True)
class MaintenancePrincipal:
    operator_id: str
    capabilities: frozenset[str]
    expires_at: datetime


def _protected_file(path_value, *, setting_name):
    if not isinstance(path_value, str) or not path_value:
        raise ImproperlyConfigured(f"{setting_name} is required")
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    resolved = path.resolve(strict=True)
    repository = Path(settings.REPOSITORY_DIR).resolve()
    if resolved == repository or repository in resolved.parents:
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    mode = resolved.stat().st_mode
    if os.name != "nt":
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    else:
        try:
            output = subprocess.run(
                ["icacls", str(resolved)], check=True, capture_output=True, text=True,
                timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.lower()
        except (OSError, subprocess.SubprocessError):
            raise MaintenanceAuthorizationDenied("Maintenance authorization denied") from None
        if any(principal in output for principal in ("everyone:", "builtin\\users:",
                                                     "authenticated users:", "everyone:(")):
            raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    return resolved


def _key(path_value, *, setting_name):
    path = _protected_file(path_value, setting_name=setting_name)
    value = path.read_bytes()
    if len(value) < 32 or len(value) > 4096:
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    return value


def _canonical(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def authenticate_maintenance_operator(*, operator_id, token_file, required_capability, now=None):
    if required_capability not in CAPABILITIES or not isinstance(operator_id, str) or not _OPERATOR_ID.fullmatch(operator_id):
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    auth_path = _protected_file(
        getattr(settings, "VAULT_MAINTENANCE_OPERATORS_FILE", ""),
        setting_name="VAULT_MAINTENANCE_OPERATORS_FILE",
    )
    auth_key = _key(
        getattr(settings, "VAULT_MAINTENANCE_AUTH_KEY_FILE", ""),
        setting_name="VAULT_MAINTENANCE_AUTH_KEY_FILE",
    )
    supplied_token = _protected_file(token_file, setting_name="operator token file").read_bytes()
    if not 32 <= len(supplied_token) <= 4096:
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied")
    try:
        document = json.loads(auth_path.read_text(encoding="utf-8"))
        mac = document.pop("mac")
        if document.get("schemaVersion") != SCHEMA_VERSION or set(document) != {"schemaVersion", "operators"}:
            raise ValueError
        expected_mac = hmac.new(auth_key, b"vault-maintenance-auth-file-v1\x00" + _canonical(document), hashlib.sha256).hexdigest()
        if not isinstance(mac, str) or not hmac.compare_digest(mac, expected_mac):
            raise ValueError
        entries = [entry for entry in document["operators"] if entry.get("operatorId") == operator_id]
        if len(entries) != 1:
            raise ValueError
        entry = entries[0]
        if set(entry) != {"operatorId", "enabled", "capabilities", "expiresAt", "tokenDigest"}:
            raise ValueError
        capabilities = frozenset(entry["capabilities"])
        expires_at = datetime.fromisoformat(entry["expiresAt"])
        now = now or datetime.now(timezone.utc)
        token_digest = hmac.new(auth_key, b"vault-maintenance-operator-token-v1\x00" + supplied_token,
                                hashlib.sha256).hexdigest()
        if (not entry["enabled"] or expires_at.tzinfo is None or expires_at <= now or
                not capabilities <= CAPABILITIES or required_capability not in capabilities or
                not isinstance(entry["tokenDigest"], str) or not _HEX_64.fullmatch(entry["tokenDigest"]) or
                not hmac.compare_digest(entry["tokenDigest"], token_digest)):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise MaintenanceAuthorizationDenied("Maintenance authorization denied") from None
    return MaintenancePrincipal(operator_id=operator_id, capabilities=capabilities, expires_at=expires_at)


def digest_parameters(parameters):
    return hashlib.sha256(b"vault-maintenance-parameters-v1\x00" + _canonical(parameters)).hexdigest()
