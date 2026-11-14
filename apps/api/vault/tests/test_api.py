from django.test import Client, TestCase

from accounts.models import User
from vault.models import VaultRecord


class VaultApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("api-owner@example.test", "password")

    def test_anonymous_metadata_and_sensitive_routes_require_authentication(self):
        client = Client()
        self.assertEqual(client.get("/api/v1/vault/credentials").status_code, 401)
        self.assertEqual(client.post("/api/v1/vault/credentials", {}).status_code, 401)

    def test_sensitive_production_routes_require_csrf_and_grant(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post("/api/v1/vault/credentials", {}).status_code, 403)
        token_response = client.get("/api/v1/auth/csrf")
        token = token_response.json()["csrfToken"]
        response = client.post("/api/v1/vault/credentials", {}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "invalid_grant")

    def test_metadata_list_is_owner_scoped_and_contains_no_envelope(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/api/v1/vault/credentials")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"credentials": [], "nextCursor": None})

    def test_metadata_list_uses_bounded_keyset_cursor(self):
        for index in range(3):
            VaultRecord.objects.create(owner=self.user, credential_type="LOGIN", label=f"Item {index}", key_version=1,
                                       nonce=b"n" * 12, ciphertext=b"ciphertext", tag=b"t" * 16)
        client = Client()
        client.force_login(self.user)
        first = client.get("/api/v1/vault/credentials?limit=2").json()
        self.assertEqual(len(first["credentials"]), 2)
        self.assertIsNotNone(first["nextCursor"])
        second = client.get("/api/v1/vault/credentials", {"limit": 2, "cursor": first["nextCursor"]}).json()
        self.assertEqual(len(second["credentials"]), 1)
        self.assertTrue({item["id"] for item in first["credentials"]}.isdisjoint(item["id"] for item in second["credentials"]))
