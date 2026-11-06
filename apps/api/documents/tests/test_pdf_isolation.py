import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from documents.pdf_isolation import PdfIsolationFailure, PdfPreflightRejected, run_isolated_pdf_preflight


class PdfPreflightIsolationTests(SimpleTestCase):
    module = "documents.tests.pdf_worker_fixture"

    def path(self):
        temporary = tempfile.NamedTemporaryFile(delete=False)
        temporary.close()
        path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    @override_settings(DOCUMENT_PDF_PREFLIGHT_TIMEOUT_SECONDS=1)
    def test_timeout_terminates_contained_process_tree(self):
        started = time.monotonic()
        with self.assertRaises(PdfPreflightRejected):
            run_isolated_pdf_preflight(
                self.path(),
                module=self.module,
                extra_env={"DOCUMENT_PDF_FIXTURE_MODE": "timeout"},
            )
        self.assertLess(time.monotonic() - started, 10)

    @override_settings(DOCUMENT_PDF_PREFLIGHT_MEMORY_BYTES=128 * 1024 * 1024)
    def test_job_memory_exhaustion_is_rejected(self):
        with self.assertRaises(PdfPreflightRejected):
            run_isolated_pdf_preflight(
                self.path(),
                module=self.module,
                extra_env={"DOCUMENT_PDF_FIXTURE_MODE": "memory"},
            )

    def test_subprocess_failure_fails_closed(self):
        with self.assertRaises(PdfIsolationFailure):
            run_isolated_pdf_preflight(
                self.path(),
                module=self.module,
                extra_env={"DOCUMENT_PDF_FIXTURE_MODE": "failure"},
            )

    def test_successful_bounded_child_returns_page_count(self):
        self.assertEqual(run_isolated_pdf_preflight(self.path(), module=self.module), 1)
