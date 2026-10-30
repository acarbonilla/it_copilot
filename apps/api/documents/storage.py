import hashlib
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


_STORAGE_KEY = re.compile(
    r"^(?:originals/[0-9a-f]{2}/[0-9a-f]{32}\.bin|extracted/[0-9a-f]{32}/[0-9a-f]{32}\.txt)$"
)


class ArtifactStorageError(Exception):
    pass


class ArtifactTooLarge(ArtifactStorageError):
    pass


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    sha256_digest: str
    byte_length: int


def _is_reparse_point(path):
    details = path.lstat()
    return stat.S_ISLNK(details.st_mode) or bool(
        getattr(details, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


class PrivateArtifactStore:
    def __init__(self, root=None):
        configured = Path(root if root is not None else settings.DOCUMENT_PRIVATE_STORAGE_ROOT)
        if not configured.is_absolute():
            configured = settings.REPOSITORY_DIR / configured
        self.root = configured.absolute()
        self._prepare_root()

    def _prepare_root(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir() or _is_reparse_point(self.root):
            raise ImproperlyConfigured("Private document storage root must be a real directory")
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current = current / part
            if current.exists() and _is_reparse_point(current):
                raise ImproperlyConfigured("Private document storage path cannot contain a reparse point")
        resolved = self.root.resolve(strict=True)
        forbidden = (
            settings.REPOSITORY_DIR / "apps" / "web" / "public",
            settings.API_DIR / "media",
            settings.API_DIR / "static",
            settings.API_DIR / "staticfiles",
        )
        for public_root in forbidden:
            public_root = public_root.absolute()
            if resolved == public_root or resolved.is_relative_to(public_root):
                raise ImproperlyConfigured("Private document storage cannot be inside a served directory")
        self._resolved_root = resolved
        from .windows_acl import enforce_and_verify_private_acl, lock_directory_against_replacement

        self.allowed_acl_sids = enforce_and_verify_private_acl(self.root)
        self._root_lock = lock_directory_against_replacement(self.root)

    def close(self):
        lock = getattr(self, "_root_lock", None)
        if lock:
            lock.close()
            self._root_lock = None

    def __del__(self):
        self.close()

    def _assert_private_path(self, path, *, require_exists=False):
        candidate = path.resolve(strict=require_exists)
        if candidate == self._resolved_root or not candidate.is_relative_to(self._resolved_root):
            raise ArtifactStorageError("Artifact path escaped private storage")
        current = self.root
        relative = path.absolute().relative_to(self.root)
        parts = relative.parts if require_exists else relative.parts[:-1]
        for part in parts:
            current = current / part
            if current.exists() and _is_reparse_point(current):
                raise ArtifactStorageError("Artifact path contains a reparse point")
        return candidate

    def write_upload(self, uploaded_file):
        artifact_id = uuid.uuid4().hex
        storage_key = f"originals/{artifact_id[:2]}/{artifact_id}.bin"
        destination = self.root / Path(*storage_key.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._assert_private_path(destination)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = None
        byte_length = 0
        digest = hashlib.sha256()
        try:
            descriptor = os.open(destination, flags, 0o600)
            with os.fdopen(descriptor, "wb") as artifact:
                descriptor = None
                for chunk in uploaded_file.chunks():
                    if not isinstance(chunk, bytes):
                        chunk = bytes(chunk)
                    byte_length += len(chunk)
                    if byte_length > settings.DOCUMENT_MAX_FILE_BYTES:
                        raise ArtifactTooLarge("Upload exceeds the configured file limit")
                    digest.update(chunk)
                    artifact.write(chunk)
                artifact.flush()
                os.fsync(artifact.fileno())
            if byte_length == 0:
                raise ArtifactStorageError("Empty artifacts are not accepted")
            self._assert_private_path(destination, require_exists=True)
            return StoredArtifact(storage_key, digest.hexdigest(), byte_length)
        except Exception as original_error:
            if descriptor is not None:
                os.close(descriptor)
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                try:
                    self.quarantine(storage_key)
                except Exception as cleanup_error:
                    raise ArtifactStorageError("Partial private artifact requires reconciliation") from cleanup_error
            raise original_error

    def resolve(self, storage_key):
        if not isinstance(storage_key, str) or not _STORAGE_KEY.fullmatch(storage_key):
            raise ArtifactStorageError("Artifact identifier is invalid")
        path = self.root / Path(*storage_key.split("/"))
        try:
            self._assert_private_path(path, require_exists=True)
        except OSError as exc:
            raise ArtifactStorageError("Artifact is unavailable") from exc
        if not path.is_file() or _is_reparse_point(path):
            raise ArtifactStorageError("Artifact is not a private regular file")
        return path

    def allocate_extracted_path(self, version_id):
        version_hex = getattr(version_id, "hex", None)
        if not isinstance(version_hex, str) or not re.fullmatch(r"[0-9a-f]{32}", version_hex):
            raise ArtifactStorageError("Document version identifier is invalid")
        storage_key = f"extracted/{version_hex}/{uuid.uuid4().hex}.txt"
        path = self.root / Path(*storage_key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._assert_private_path(path)
        return storage_key, path

    def inspect_text(self, storage_key):
        path = self.resolve(storage_key)
        digest = hashlib.sha256()
        byte_length = 0
        decoder_chunks = []
        try:
            with path.open("rb") as source:
                while chunk := source.read(64 * 1024):
                    byte_length += len(chunk)
                    digest.update(chunk)
                    decoder_chunks.append(chunk)
            text = b"".join(decoder_chunks).decode("utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as exc:
            raise ArtifactStorageError("Extracted artifact is invalid") from exc
        if not text or len(text) > settings.DOCUMENT_EXTRACTION_MAX_CHARACTERS:
            raise ArtifactStorageError("Extracted artifact violates its content bound")
        return StoredArtifact(storage_key, digest.hexdigest(), byte_length), len(text)

    def delete(self, storage_key):
        path = self.resolve(storage_key)
        path.unlink()

    def quarantine(self, storage_key):
        source = self.resolve(storage_key)
        quarantine_root = self.root / "quarantine"
        quarantine_root.mkdir(parents=True, exist_ok=True)
        destination = quarantine_root / f"{uuid.uuid4().hex}.orphan"
        self._assert_private_path(destination)
        os.replace(source, destination)
        return destination

    def inventory_keys(self):
        keys = []
        for namespace in ("originals", "extracted"):
            root = self.root / namespace
            if not root.exists():
                continue
            if _is_reparse_point(root):
                raise ArtifactStorageError("Artifact inventory contains a reparse point")
            for path in root.rglob("*"):
                if path.is_dir():
                    if _is_reparse_point(path):
                        raise ArtifactStorageError("Artifact inventory contains a reparse point")
                    continue
                key = path.relative_to(self.root).as_posix()
                self.resolve(key)
                keys.append(key)
        return sorted(keys)

    def restore_quarantined(self, quarantine_path, storage_key):
        quarantine_root = (self.root / "quarantine").resolve(strict=True)
        source = Path(quarantine_path).resolve(strict=True)
        if not source.is_relative_to(quarantine_root) or _is_reparse_point(source):
            raise ArtifactStorageError("Quarantine artifact is invalid")
        destination = self.root / Path(*storage_key.split("/"))
        self._assert_private_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ArtifactStorageError("Artifact restore target already exists")
        os.replace(source, destination)
