from django.test import Client, SimpleTestCase, TestCase, override_settings

from accounts.models import User
from vault.models import VaultRecord


@override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:3000"])
class VaultCorsTests(SimpleTestCase):
    def test_vault_grant_header_is_allowed_only_for_approved_origin(self):
        requested_headers = "content-type,x-csrftoken,x-vault-grant"
        approved = self.client.options(
            "/api/v1/vault/credentials",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=requested_headers,
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved["Access-Control-Allow-Origin"], "http://localhost:3000")
        allowed_headers = {value.strip() for value in approved["Access-Control-Allow-Headers"].split(",")}
        self.assertIn("x-csrftoken", allowed_headers)
        self.assertIn("x-vault-grant", allowed_headers)

        unapproved = self.client.options(
            "/api/v1/vault/credentials",
            HTTP_ORIGIN="https://unapproved.example.test",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=requested_headers,
        )
        self.assertNotIn("Access-Control-Allow-Origin", unapproved)


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
