import json
import os
import subprocess
import sys

from django.conf import settings


class PdfPreflightRejected(Exception):
    pass


class PdfIsolationFailure(Exception):
    pass


def run_isolated_pdf_preflight(path, *, module="documents.pdf_preflight_worker", extra_env=None):
    if os.name != "nt":
        raise PdfIsolationFailure("PDF preflight isolation is unavailable")
    from .windows_job import WindowsJob

    timeout = settings.DOCUMENT_PDF_PREFLIGHT_TIMEOUT_SECONDS
    memory_limit = settings.DOCUMENT_PDF_PREFLIGHT_MEMORY_BYTES
    if timeout <= 0 or memory_limit <= 0:
        raise PdfIsolationFailure("PDF preflight limits are invalid")

    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    process = None
    job = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=settings.API_DIR,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        job = WindowsJob(memory_limit_bytes=memory_limit)
        job.assign(process._handle)
        payload = json.dumps({"path": str(path)}, separators=(",", ":")).encode("utf-8") + b"\n"
        stdout, _ = process.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if job:
            job.terminate(2)
        if process:
            process.wait(timeout=10)
        raise PdfPreflightRejected("PDF preflight exceeded its deadline") from exc
    except Exception as exc:
        if job:
            job.terminate(3)
        if process:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        raise PdfIsolationFailure("PDF preflight could not be isolated") from exc
    finally:
        if job:
            job.close()

    if len(stdout) > 4096:
        raise PdfIsolationFailure("PDF preflight response exceeded its bound")
    try:
        result = json.loads(stdout.decode("utf-8"))
    except Exception as exc:
        raise PdfIsolationFailure("PDF preflight returned an invalid response") from exc
    if process.returncode == 0 and result.get("ok") is True and isinstance(result.get("pages"), int):
        return result["pages"]
    if process.returncode in {2, 3} and result.get("ok") is False:
        raise PdfPreflightRejected("PDF preflight rejected the artifact")
    raise PdfIsolationFailure("PDF preflight subprocess failed")
