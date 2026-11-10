import base64
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from vault.crypto import VaultCryptoError
from vault.keys import load_kek


class VaultKeyLoaderTests(SimpleTestCase):
    def test_injected_key_and_file_key_are_exactly_32_bytes(self):
        encoded = base64.b64encode(b"k" * 32).decode("ascii")
        with mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": encoded}, clear=False), override_settings(VAULT_KEK_FILE=""):
            self.assertEqual(load_kek(), b"k" * 32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vault-key"
            path.write_text(encoded, encoding="ascii")
            with mock.patch.dict(os.environ, {}, clear=True), override_settings(VAULT_KEK_FILE=str(path)):
                self.assertEqual(load_kek(), b"k" * 32)

    def test_missing_ambiguous_malformed_and_wrong_length_keys_fail_closed(self):
        cases = ["", "not-base64", base64.b64encode(b"short").decode("ascii")]
        for value in cases:
            environment = {"VAULT_KEK_BASE64": value} if value else {}
            with self.subTest(value=bool(value)), mock.patch.dict(os.environ, environment, clear=True), override_settings(VAULT_KEK_FILE=""):
                with self.assertRaisesRegex(VaultCryptoError, "Vault key material is unavailable"):
                    load_kek()
        encoded = base64.b64encode(b"k" * 32).decode("ascii")
        with mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": encoded}, clear=True), override_settings(VAULT_KEK_FILE="also-set"):
            with self.assertRaises(VaultCryptoError):
                load_kek()
