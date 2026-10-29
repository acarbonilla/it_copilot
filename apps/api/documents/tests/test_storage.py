import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from documents.storage import ArtifactStorageError, ArtifactTooLarge, PrivateArtifactStore
from documents.windows_acl import verify_private_acl


class PrivateArtifactStoreTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "private"

    def private_store(self, root=None):
        store = PrivateArtifactStore(root or self.root)
        self.addCleanup(store.close)
        return store

    @override_settings(DOCUMENT_MAX_FILE_BYTES=8)
    def test_exclusive_opaque_write_digest_and_size(self):
        store = self.private_store()
        self.assertEqual(store.allowed_acl_sids, verify_private_acl(self.root))
        self.assertEqual(len(store.allowed_acl_sids), 2)
        upload = SimpleUploadedFile("../../secret-name.txt", b"private", content_type="text/plain")
        stored = store.write_upload(upload)
        self.assertRegex(stored.storage_key, r"^originals/[0-9a-f]{2}/[0-9a-f]{32}\.bin$")
        self.assertNotIn("secret", stored.storage_key)
        self.assertEqual(stored.byte_length, 7)
        self.assertEqual(stored.sha256_digest, hashlib.sha256(b"private").hexdigest())
        self.assertEqual(store.resolve(stored.storage_key).read_bytes(), b"private")

    @override_settings(DOCUMENT_MAX_FILE_BYTES=4)
    def test_streamed_size_limit_removes_partial_artifact(self):
        store = self.private_store()
        upload = SimpleUploadedFile("large.txt", b"12345", content_type="text/plain")
        with self.assertRaises(ArtifactTooLarge):
            store.write_upload(upload)
        self.assertEqual([path for path in self.root.rglob("*") if path.is_file()], [])

    @override_settings(DOCUMENT_MAX_FILE_BYTES=4)
    def test_partial_write_cleanup_failure_moves_artifact_to_private_quarantine(self):
        store = self.private_store()
        upload = SimpleUploadedFile("large.txt", b"12345", content_type="text/plain")
        with patch("pathlib.Path.unlink", side_effect=OSError("delete failure")), self.assertRaises(ArtifactTooLarge):
            store.write_upload(upload)
        files = [path for path in self.root.rglob("*") if path.is_file()]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].parent.name, "quarantine")

    def test_invalid_storage_key_cannot_resolve_filename_or_traversal(self):
        store = self.private_store()
        for key in ("../../outside", "originals/file.txt", "originals/aa/not-a-uuid.bin"):
            with self.subTest(key=key), self.assertRaises(ArtifactStorageError):
                store.resolve(key)

    def test_storage_inside_a_served_root_is_rejected(self):
        repository = Path(self.temporary.name) / "repository"
        public = repository / "apps" / "web" / "public"
        with override_settings(REPOSITORY_DIR=repository, API_DIR=repository / "apps" / "api"):
            with self.assertRaises(ImproperlyConfigured):
                self.private_store(public / "documents")

    @skipUnless(os.name == "nt", "Windows ACL trust-boundary evidence")
    def test_acl_verification_rejects_new_untrusted_write_principal(self):
        store = self.private_store()
        result = subprocess.run(
            ["icacls", str(self.root), "/grant", "*S-1-1-0:(OI)(CI)F"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        with self.assertRaises(ImproperlyConfigured):
            verify_private_acl(self.root)

    @skipUnless(os.name == "nt", "Windows replacement-lock evidence")
    def test_storage_root_cannot_be_renamed_while_store_is_active(self):
        store = self.private_store()
        with self.assertRaises(PermissionError):
            self.root.rename(self.root.with_name("redirected"))

    @skipUnless(os.name == "nt", "Windows junction/reparse-point evidence")
    def test_windows_junction_escape_is_rejected(self):
        store = self.private_store()
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        artifact_name = "a" * 32 + ".bin"
        (outside / artifact_name).write_bytes(b"outside")
        originals = self.root / "originals"
        originals.mkdir()
        junction = originals / "aa"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        try:
            with self.assertRaises(ArtifactStorageError):
                store.resolve(f"originals/aa/{artifact_name}")
        finally:
            os.rmdir(junction)
