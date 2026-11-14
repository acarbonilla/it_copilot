import os
from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from vault.crypto import EncryptionContext, VaultCryptoError, decrypt, encrypt, unwrap_dek, wrap_dek


class VaultCryptoTests(SimpleTestCase):
    def setUp(self):
        self.key = b"k" * 32
        self.context = EncryptionContext(1, "12345678-1234-4234-8234-123456789abc", "LOGIN")

    def test_round_trip_and_fresh_nonces(self):
        first = encrypt(dek=self.key, plaintext=b"opaque-test-value", context=self.context, key_version=1)
        second = encrypt(dek=self.key, plaintext=b"opaque-test-value", context=self.context, key_version=1)
        self.assertEqual(decrypt(dek=self.key, envelope=first, context=self.context), b"opaque-test-value")
        self.assertNotEqual(first.nonce, second.nonce)
        self.assertNotEqual(first.ciphertext, second.ciphertext)

    def test_tampering_and_aad_substitution_fail_closed(self):
        envelope = encrypt(dek=self.key, plaintext=b"opaque-test-value", context=self.context, key_version=1)
        variants = [
            (replace(envelope, ciphertext=bytes([envelope.ciphertext[0] ^ 1]) + envelope.ciphertext[1:]), self.context),
            (replace(envelope, tag=bytes([envelope.tag[0] ^ 1]) + envelope.tag[1:]), self.context),
            (replace(envelope, nonce=bytes([envelope.nonce[0] ^ 1]) + envelope.nonce[1:]), self.context),
            (envelope, replace(self.context, owner_id=2)),
            (envelope, replace(self.context, record_id="different")),
            (envelope, replace(self.context, credential_type="API_TOKEN")),
            (replace(envelope, envelope_version=99), self.context),
        ]
        for candidate, context in variants:
            with self.subTest(candidate=candidate, context=context), self.assertRaisesRegex(VaultCryptoError, "Vault"):
                decrypt(dek=self.key, envelope=candidate, context=context)

    def test_wrong_or_malformed_keys_are_secret_free(self):
        envelope = encrypt(dek=self.key, plaintext=b"opaque-test-value", context=self.context, key_version=1)
        for key in (b"x" * 32, b"short", None):
            with self.subTest(key=key), self.assertRaises(VaultCryptoError) as caught:
                decrypt(dek=key, envelope=envelope, context=self.context)
            self.assertNotIn("opaque-test-value", str(caught.exception))

    def test_dek_wrap_round_trip_and_owner_binding(self):
        wrapped = wrap_dek(kek=b"e" * 32, dek=self.key, owner_id=1, key_version=3)
        self.assertEqual(unwrap_dek(kek=b"e" * 32, envelope=wrapped, owner_id=1), self.key)
        with self.assertRaises(VaultCryptoError):
            unwrap_dek(kek=b"e" * 32, envelope=wrapped, owner_id=2)

    @mock.patch("vault.crypto.os.urandom", side_effect=OSError("provider detail"))
    def test_nonce_provider_failure_is_secret_free(self, _urandom):
        with self.assertRaisesRegex(VaultCryptoError, "Vault encryption failed"):
            encrypt(dek=self.key, plaintext=b"opaque-test-value", context=self.context, key_version=1)
