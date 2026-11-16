import os
import stat
import subprocess
from pathlib import Path

from django.conf import settings

from .backup_contracts import BackupContractError


_BROAD_WINDOWS_PRINCIPALS = ("everyone:", "builtin\\users:", "authenticated users:")


def validate_protected_root(path_value, *, permitted_sids=()):
    if not isinstance(path_value, str) or not path_value:
        raise BackupContractError("Protected backup root is invalid")
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise BackupContractError("Protected backup root is invalid")
    resolved = path.resolve(strict=True)
    repository = Path(settings.REPOSITORY_DIR).resolve(strict=True)
    if resolved == repository or repository in resolved.parents:
        raise BackupContractError("Protected backup root is invalid")
    for parent in (resolved, *resolved.parents):
        if parent.is_symlink():
            raise BackupContractError("Protected backup root is invalid")
        if os.name == "nt" and getattr(os.lstat(parent), "st_file_attributes", 0) & 0x400:
            raise BackupContractError("Protected backup root is invalid")
    if os.name == "nt":
        try:
            output = subprocess.run(["icacls", str(resolved)], check=True, capture_output=True, text=True,
                                    timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
        except (OSError, subprocess.SubprocessError):
            raise BackupContractError("Protected backup ACL validation failed") from None
        if any(principal in output for principal in _BROAD_WINDOWS_PRINCIPALS):
            raise BackupContractError("Protected backup ACL is invalid")
        if permitted_sids and not all(sid.lower() in output for sid in permitted_sids):
            raise BackupContractError("Protected backup ACL is invalid")
    elif resolved.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise BackupContractError("Protected backup ACL is invalid")
    return resolved


def validate_artifact(path, *, root):
    path = Path(path)
    root = Path(root).resolve(strict=True)
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root:
        raise BackupContractError("Backup artifact is invalid")
    return path.resolve(strict=True)
