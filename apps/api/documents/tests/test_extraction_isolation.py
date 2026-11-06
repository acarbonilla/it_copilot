import hashlib
import os
import tempfile
import time
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase, override_settings

from documents.extraction_isolation import (
    ExtractionInfrastructureFailure,
    ExtractionRejected,
    run_isolated_extraction,
)


@skipUnless(os.name == "nt", "Windows Job Object extraction evidence")
class ExtractionIsolationTests(SimpleTestCase):
    @staticmethod
    def simple_pdf():
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length 37 >>\nstream\nBT /F1 12 Tf 72 72 Td (Hello) Tj ET\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        data = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, body in enumerate(objects, 1):
            offsets.append(len(data))
            data.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
        xref = len(data)
        data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        data.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            data.extend(f"{offset:010d} 00000 n \n".encode())
        data.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(data)

    def paths(self, content=b"first\r\nsecond\r"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "input.bin"
        output = root / "output.txt"
        source.write_bytes(content)
        return source, output

    def test_real_text_extraction_normalizes_utf8(self):
        source, output = self.paths()
        result = run_isolated_extraction(input_path=source, output_path=output, media_type="text/plain")
        self.assertEqual(output.read_text(encoding="utf-8"), "first\nsecond\n")
        self.assertEqual(result.character_count, 13)
        self.assertEqual(result.sha256_digest, hashlib.sha256(output.read_bytes()).hexdigest())

    def test_real_pdf_extraction_returns_text_and_page_count(self):
        source, output = self.paths(self.simple_pdf())
        result = run_isolated_extraction(input_path=source, output_path=output, media_type="application/pdf")
        self.assertEqual(output.read_text(encoding="utf-8").strip(), "Hello")
        self.assertEqual(result.page_count, 1)

    def test_markdown_is_treated_as_inert_utf8_text(self):
        source, output = self.paths(b"# Heading\r\n<script>not executed</script>")
        result = run_isolated_extraction(input_path=source, output_path=output, media_type="text/markdown")
        self.assertIn("<script>not executed</script>", output.read_text(encoding="utf-8"))
        self.assertIsNone(result.page_count)

    def test_corrupted_pdf_is_rejected_without_output(self):
        source, output = self.paths(b"%PDF-1.4\ncorrupt")
        with self.assertRaises(ExtractionRejected) as caught:
            run_isolated_extraction(input_path=source, output_path=output, media_type="application/pdf")
        self.assertEqual(caught.exception.code, "invalid")
        self.assertFalse(output.exists())

    @override_settings(DOCUMENT_EXTRACTION_MAX_CHARACTERS=2_000_000)
    def test_character_limit_is_terminal(self):
        source, output = self.paths(b"x" * 2_000_001)
        with self.assertRaises(ExtractionRejected) as caught:
            run_isolated_extraction(input_path=source, output_path=output, media_type="text/plain")
        self.assertEqual(caught.exception.code, "character_limit")
        self.assertFalse(output.exists())

    @override_settings(DOCUMENT_EXTRACTION_TIMEOUT_SECONDS=1)
    def test_timeout_terminates_process_tree(self):
        source, output = self.paths()
        started = time.monotonic()
        with self.assertRaises(ExtractionRejected) as caught:
            run_isolated_extraction(
                input_path=source,
                output_path=output,
                media_type="text/plain",
                module="documents.tests.extraction_worker_fixture",
                extra_env={"DOCUMENT_EXTRACTION_FIXTURE": "timeout"},
            )
        self.assertEqual(caught.exception.code, "timeout")
        self.assertLess(time.monotonic() - started, 10)

    @override_settings(DOCUMENT_EXTRACTION_MEMORY_BYTES=128 * 1024 * 1024)
    def test_job_memory_exhaustion_is_rejected(self):
        source, output = self.paths()
        with self.assertRaises(ExtractionRejected) as caught:
            run_isolated_extraction(
                input_path=source,
                output_path=output,
                media_type="text/plain",
                module="documents.tests.extraction_worker_fixture",
                extra_env={"DOCUMENT_EXTRACTION_FIXTURE": "memory"},
            )
        self.assertEqual(caught.exception.code, "resource_limit")

    def test_subprocess_failure_is_fail_closed(self):
        source, output = self.paths()
        with self.assertRaises(ExtractionInfrastructureFailure):
            run_isolated_extraction(
                input_path=source,
                output_path=output,
                media_type="text/plain",
                module="documents.tests.extraction_worker_fixture",
                extra_env={"DOCUMENT_EXTRACTION_FIXTURE": "failure"},
            )

    @override_settings(DOCUMENT_JOB_HEARTBEAT_SECONDS=1)
    def test_heartbeat_loss_terminates_child(self):
        source, output = self.paths()
        with self.assertRaises(ExtractionInfrastructureFailure):
            run_isolated_extraction(
                input_path=source,
                output_path=output,
                media_type="text/plain",
                heartbeat=lambda: False,
                module="documents.tests.extraction_worker_fixture",
                extra_env={"DOCUMENT_EXTRACTION_FIXTURE": "timeout"},
            )
