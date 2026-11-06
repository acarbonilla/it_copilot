import json

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.http import HttpResponse

from documents.middleware import DocumentUploadSizeMiddleware


class DocumentUploadSizeMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def invoke(self, content_length):
        reached = []

        def next_handler(request):
            reached.append(True)
            return HttpResponse(status=204)

        request = self.factory.post(
            "/api/v1/documents",
            data=b"unparsed multipart body",
            content_type="multipart/form-data; boundary=x",
        )
        if content_length is None:
            request.META.pop("CONTENT_LENGTH", None)
        else:
            request.META["CONTENT_LENGTH"] = content_length
        response = DocumentUploadSizeMiddleware(next_handler)(request)
        return response, reached

    def test_missing_malformed_and_nonpositive_lengths_fail_before_body_parsing(self):
        for value in (None, "not-a-number", "0", "-1"):
            with self.subTest(value=value):
                response, reached = self.invoke(value)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(json.loads(response.content)["error"]["code"], "invalid_upload")
                self.assertEqual(reached, [])

    @override_settings(DOCUMENT_MAX_REQUEST_BYTES=8)
    def test_oversized_length_fails_before_body_parsing(self):
        response, reached = self.invoke("9")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(json.loads(response.content)["error"]["code"], "request_too_large")
        self.assertEqual(reached, [])

    def test_valid_length_continues_without_accessing_request_body(self):
        response, reached = self.invoke("64")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(reached, [True])
