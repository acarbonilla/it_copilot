import hashlib
import uuid

from django.db import DatabaseError, transaction

from .extraction_isolation import (
    ExtractionInfrastructureFailure,
    ExtractionRejected,
    run_isolated_extraction,
)
from .artifact_coordination import lock_artifact_publication
from .jobs import LeaseLost, claim_next_job, fail_claim, heartbeat, publish_claim
from .models import ExtractedTextArtifact, OriginalArtifact, QuarantinedArtifact
from .storage import ArtifactStorageError, PrivateArtifactStore


class ArtifactCompensationUnresolved(Exception):
    pass


def _compensate_extracted(store, storage_key):
    """Remove only a definitely unreferenced result under the publication guard."""
    try:
        with transaction.atomic():
            lock_artifact_publication()
            if (
                OriginalArtifact.objects.filter(storage_key=storage_key).exists()
                or ExtractedTextArtifact.objects.filter(storage_key=storage_key).exists()
            ):
                return "referenced"
            if QuarantinedArtifact.objects.filter(storage_key=storage_key).exists():
                return "quarantined"
            try:
                store.delete(storage_key)
                return "deleted"
            except ArtifactStorageError:
                # Missing already means there is nothing left to compensate.
                return "absent"
            except Exception:
                try:
                    store.quarantine(storage_key)
                    return "quarantined"
                except Exception as exc:
                    raise ArtifactCompensationUnresolved(
                        "Extracted artifact cleanup requires reconciliation"
                    ) from exc
    except ArtifactCompensationUnresolved:
        raise
    except Exception as exc:
        # Reference state is uncertain. Preserve the file for later reconciliation.
        raise ArtifactCompensationUnresolved(
            "Extracted artifact reference state could not be verified"
        ) from exc


def _fail_safely(claim, *, error_code, retryable):
    try:
        return fail_claim(claim, error_code=error_code, retryable=retryable)
    except LeaseLost:
        return "stale"


def _original_path(store, claim):
    artifact = OriginalArtifact.objects.get(document_version_id=claim.version_id)
    path = store.resolve(artifact.storage_key)
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            length += len(chunk)
            digest.update(chunk)
    if length != artifact.byte_length or digest.hexdigest() != artifact.sha256_digest:
        raise ArtifactStorageError("Original artifact integrity check failed")
    return artifact, path


def process_one(*, worker_id=None, store=None, extraction_runner=run_isolated_extraction):
    worker_id = uuid.UUID(str(worker_id)) if worker_id else uuid.uuid4()
    claim = claim_next_job(worker_id=worker_id)
    if claim is None:
        return None
    owned_store = store is None
    store = store or PrivateArtifactStore()
    storage_key = None
    try:
        try:
            original, input_path = _original_path(store, claim)
            storage_key, output_path = store.allocate_extracted_path(claim.version_id)
            result = extraction_runner(
                input_path=input_path,
                output_path=output_path,
                media_type=original.detected_media_type,
                heartbeat=lambda: heartbeat(claim),
            )
            stored, characters = store.inspect_text(storage_key)
            if (
                characters != result.character_count
                or stored.byte_length != result.byte_length
                or stored.sha256_digest != result.sha256_digest
            ):
                raise ArtifactStorageError("Extracted artifact integrity check failed")
            publish_claim(
                claim,
                stored=stored,
                character_count=characters,
                page_count=result.page_count,
                extractor_version=result.extractor_version,
                store=store,
            )
            storage_key = None
            return "succeeded"
        except ExtractionRejected as exc:
            state = _fail_safely(
                claim,
                error_code=exc.code,
                retryable=exc.code in {"timeout", "resource_limit", "parser_failure"},
            )
            return "stale" if state == "stale" else "failed"
        except (ExtractionInfrastructureFailure, OSError):
            state = _fail_safely(claim, error_code="worker_failure", retryable=True)
            return "stale" if state == "stale" else "retry"
        except (ArtifactStorageError, OriginalArtifact.DoesNotExist):
            state = _fail_safely(claim, error_code="artifact_invalid", retryable=False)
            return "stale" if state == "stale" else "failed"
        except LeaseLost:
            return "stale"
        except DatabaseError:
            state = _fail_safely(claim, error_code="database_failure", retryable=True)
            return "stale" if state == "stale" else "retry"
    finally:
        if storage_key is not None:
            _compensate_extracted(store, storage_key)
        if owned_store:
            store.close()
