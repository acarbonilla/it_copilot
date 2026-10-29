import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass

from django.conf import settings


class ExtractionRejected(Exception):
    def __init__(self, code="invalid"):
        self.code = code
        super().__init__(code)


class ExtractionInfrastructureFailure(Exception):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    character_count: int
    byte_length: int
    sha256_digest: str
    page_count: int | None
    extractor_version: str


def run_isolated_extraction(*, input_path, output_path, media_type, heartbeat=None, module="documents.extraction_worker", extra_env=None):
    if os.name != "nt":
        raise ExtractionInfrastructureFailure("Extraction isolation is unavailable")
    from .windows_job import WindowsJob

    timeout = settings.DOCUMENT_EXTRACTION_TIMEOUT_SECONDS
    memory_limit = settings.DOCUMENT_EXTRACTION_MEMORY_BYTES
    if timeout <= 0 or memory_limit <= 0:
        raise ExtractionInfrastructureFailure("Extraction limits are invalid")
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
        payload = json.dumps(
            {"input_path": str(input_path), "output_path": str(output_path), "media_type": media_type},
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        process.stdin.write(payload)
        process.stdin.close()
        process.stdin = None
        deadline = time.monotonic() + timeout
        heartbeat_interval = settings.DOCUMENT_JOB_HEARTBEAT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            try:
                process.wait(timeout=min(heartbeat_interval, remaining))
                break
            except subprocess.TimeoutExpired:
                if heartbeat is not None and heartbeat() is False:
                    job.terminate(5)
                    process.wait(timeout=10)
                    raise ExtractionInfrastructureFailure("Extraction lease was lost")
        stdout = process.stdout.read(4097)
    except subprocess.TimeoutExpired as exc:
        if job:
            job.terminate(2)
        if process:
            process.wait(timeout=10)
        raise ExtractionRejected("timeout") from exc
    except ExtractionInfrastructureFailure:
        raise
    except Exception as exc:
        if job:
            job.terminate(3)
        if process:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        raise ExtractionInfrastructureFailure("Extraction subprocess failed") from exc
    finally:
        if job:
            job.close()
    if len(stdout) > 4096:
        raise ExtractionInfrastructureFailure("Extraction response exceeded its bound")
    try:
        result = json.loads(stdout.decode("utf-8"))
    except Exception as exc:
        raise ExtractionInfrastructureFailure("Extraction response was invalid") from exc
    if process.returncode == 0 and result.get("ok") is True:
        try:
            return ExtractionResult(
                character_count=int(result["characters"]),
                byte_length=int(result["bytes"]),
                sha256_digest=str(result["digest"]),
                page_count=result.get("pages"),
                extractor_version=str(result["extractor"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractionInfrastructureFailure("Extraction metadata was invalid") from exc
    if process.returncode in {2, 3} and result.get("ok") is False:
        raise ExtractionRejected(result.get("code", "invalid"))
    raise ExtractionInfrastructureFailure("Extraction subprocess failed")
