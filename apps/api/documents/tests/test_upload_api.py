import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import Client, TestCase, override_settings

from accounts.models import User
from documents.models import Document, OriginalArtifact


class DocumentUploadApiTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(self.temporary.name) / "private")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user("uploader@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.client = Client(enforce_csrf_checks=True)

    def csrf_login(self, user=None):
        self.client.force_login(user or self.user)
        response = self.client.get("/api/v1/auth/csrf")
        return response.cookies["csrftoken"].value

    def payload(self):
        return {
            "title": "Runbook",
            "description": "Private",
            "file": SimpleUploadedFile("runbook.txt", b"private", content_type="text/plain"),
        }

    def test_authenticated_csrf_protected_upload_returns_only_safe_identifiers(self):
        csrf = self.csrf_login()
        response = self.client.post("/api/v1/documents", self.payload(), HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()["document"]), {"id", "version_id", "status"})
        self.assertEqual(response.json()["document"]["status"], "queued")
        self.assertEqual(Document.objects.count(), 1)
        artifact = OriginalArtifact.objects.get()
        self.assertNotIn(artifact.storage_key, str(response.content))
        self.assertNotIn(artifact.original_filename, str(response.content))

    def test_ratified_upload_limits_are_configured(self):
        self.assertEqual(settings.DOCUMENT_MAX_FILE_BYTES, 10 * 1024 * 1024)
        self.assertEqual(settings.DOCUMENT_MAX_REQUEST_BYTES, 12 * 1024 * 1024)
        self.assertEqual(settings.DOCUMENT_MAX_PDF_PAGES, 500)

    def test_authentication_csrf_role_and_request_limit_are_enforced(self):
        unauthenticated = self.client.post("/api/v1/documents", self.payload())
        self.assertEqual(unauthenticated.status_code, 403)  # CSRF rejects before view disclosure.

        anonymous_csrf = Client(enforce_csrf_checks=True)
        token_response = anonymous_csrf.get("/api/v1/auth/csrf")
        token = token_response.cookies["csrftoken"].value
        authentication_required = anonymous_csrf.post(
            "/api/v1/documents",
            self.payload(),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(authentication_required.status_code, 401)
        self.assertEqual(authentication_required.json()["error"]["code"], "authentication_required")

        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        missing_csrf = self.client.post("/api/v1/documents", self.payload())
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"]["code"], "csrf_failed")

        app_admin = User.objects.create_user("appadmin-upload@example.test", None, is_app_admin=True)
        self.client = Client(enforce_csrf_checks=True)
        csrf = self.csrf_login(app_admin)
        denied = self.client.post("/api/v1/documents", self.payload(), HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["error"]["code"], "permission_denied")

        self.client = Client(enforce_csrf_checks=True)
        csrf = self.csrf_login()
        too_large = self.client.generic(
            "POST",
            "/api/v1/documents",
            data=b"--x--",
            content_type="multipart/form-data; boundary=x",
            HTTP_X_CSRFTOKEN=csrf,
            CONTENT_LENGTH=str(12 * 1024 * 1024 + 1),
        )
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(too_large.json()["error"]["code"], "request_too_large")

    def test_invalid_format_extra_file_and_extra_field_are_generic(self):
        csrf = self.csrf_login()
        cases = (
            {
                "title": "Bad",
                "file": SimpleUploadedFile("bad.exe", b"MZ", content_type="application/octet-stream"),
            },
            {
                **self.payload(),
                "second": SimpleUploadedFile("second.txt", b"second", content_type="text/plain"),
            },
            {**self.payload(), "unexpected": "value"},
        )
        for payload in cases:
            with self.subTest(fields=tuple(payload)):
                response = self.client.post("/api/v1/documents", payload, HTTP_X_CSRFTOKEN=csrf)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"error": {"code": "invalid_upload", "message": "Document upload is invalid"}})
        self.assertFalse(Document.objects.exists())
