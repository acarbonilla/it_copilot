import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.core import signing
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import Document, DocumentVersion, ExtractedTextArtifact, OriginalArtifact, ProcessingJob
from .storage import ArtifactInventoryChanged, ArtifactStorageError, PrivateArtifactStore


DIRECTORY_ENTRY_CAP = 4096
DEFAULT_WORK_LIMIT = 5000
MAX_WORK_LIMIT = 10000
DATABASE_BATCH_SIZE = 256
CURSOR_MAX_AGE_SECONDS = 24 * 60 * 60
CURSOR_MAX_LENGTH = 4096
HASH_CHUNK_SIZE = 64 * 1024
CURSOR_SALT = "documents.reconciliation.inventory.v1"
ASSESSMENT_CURSOR_SALT = "documents.ready-consistency.v1"
PHASES = ("stale_jobs", "originals", "extracted", "filesystem_originals", "filesystem_extracted", "purge")


class InventoryCursorError(ValueError):
    pass


class InventoryWorkLimitError(ValueError):
    pass


@dataclass(frozen=True)
class RecoveryIssue:
    kind: str
    identifier: str


@dataclass(frozen=True)
class RecoveryInventoryPage:
    issues: tuple[RecoveryIssue, ...]
    next_cursor: str | None
    complete: bool
    work_performed: int


def _root_binding(store):
    return salted_hmac("documents.inventory.root", str(store._resolved_root)).hexdigest()


def _initial_state():
    return {"v": 1, "phase": PHASES[0], "position": None, "fs": None}


def _decode_cursor(cursor, *, actor_id, store):
    if cursor is None:
        return _initial_state()
    if not isinstance(cursor, str) or not cursor or len(cursor) > CURSOR_MAX_LENGTH:
        raise InventoryCursorError("Inventory cursor is invalid")
    try:
        state = signing.loads(cursor, salt=CURSOR_SALT, max_age=CURSOR_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise InventoryCursorError("Inventory cursor has expired") from exc
    except signing.BadSignature as exc:
        raise InventoryCursorError("Inventory cursor is invalid") from exc
    if not isinstance(state, dict) or state.get("v") != 1 or state.get("phase") not in PHASES:
        raise InventoryCursorError("Inventory cursor is invalid")
    if state.get("actor_id") != str(actor_id) or state.get("root") != _root_binding(store):
        raise InventoryCursorError("Inventory cursor scope is invalid")
    if state.get("cap") != DIRECTORY_ENTRY_CAP:
        raise InventoryCursorError("Inventory cursor settings are invalid")
    return {"v": 1, "phase": state["phase"], "position": state.get("position"), "fs": state.get("fs")}


def _encode_cursor(state, *, actor_id, store):
    payload = dict(state)
    payload.update({"actor_id": str(actor_id), "root": _root_binding(store), "cap": DIRECTORY_ENTRY_CAP})
    token = signing.dumps(payload, salt=CURSOR_SALT, compress=True)
    if len(token) > CURSOR_MAX_LENGTH:
        raise InventoryCursorError("Inventory cursor is too large")
    return token


def _decode_assessment_cursor(cursor, *, actor_id, store, check_physical):
    if cursor is None:
        return {"v": 1, "phase": "ready", "position": None}
    if not isinstance(cursor, str) or not cursor or len(cursor) > CURSOR_MAX_LENGTH:
        raise InventoryCursorError("Assessment cursor is invalid")
    try:
        state = signing.loads(cursor, salt=ASSESSMENT_CURSOR_SALT, max_age=CURSOR_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise InventoryCursorError("Assessment cursor has expired") from exc
    except signing.BadSignature as exc:
        raise InventoryCursorError("Assessment cursor is invalid") from exc
    if (
        not isinstance(state, dict)
        or state.get("v") != 1
        or state.get("phase") not in {"ready", "current"}
        or state.get("actor_id") != str(actor_id)
        or state.get("root") != _root_binding(store)
        or state.get("check_physical") is not bool(check_physical)
    ):
        raise InventoryCursorError("Assessment cursor scope is invalid")
    return {"v": 1, "phase": state["phase"], "position": state.get("position")}


def _assessment_page(issues, state, *, actor_id, store, check_physical, work, complete=False):
    cursor = None
    if not complete:
        payload = dict(state)
        payload.update({
            "actor_id": str(actor_id),
            "root": _root_binding(store),
            "check_physical": bool(check_physical),
        })
        cursor = signing.dumps(payload, salt=ASSESSMENT_CURSOR_SALT, compress=True)
        if len(cursor) > CURSOR_MAX_LENGTH:
            raise InventoryCursorError("Assessment cursor is too large")
    return RecoveryInventoryPage(tuple(issues), cursor, complete, work)


def assess_ready_consistency_page(*, actor_id, store=None, findings_limit=100,
                                  work_limit=DEFAULT_WORK_LIMIT, cursor=None,
                                  check_physical=False):
    """Bounded, read-only assessment of historical READY and current-version rows."""
    if (isinstance(findings_limit, bool) or not isinstance(findings_limit, int)
            or findings_limit < 1 or findings_limit > 1000):
        raise ValueError("Findings limit must be between 1 and 1000")
    if (isinstance(work_limit, bool) or not isinstance(work_limit, int)
            or work_limit < 1 or work_limit > MAX_WORK_LIMIT):
        raise InventoryWorkLimitError("Work limit must be between 1 and 10000")
    owns_store = store is None
    store = store or PrivateArtifactStore()
    work = 0
    issues = []
    maximum_chunks = math.ceil((settings.DOCUMENT_MAX_FILE_BYTES + 1) / HASH_CHUNK_SIZE)
    try:
        state = _decode_assessment_cursor(
            cursor, actor_id=actor_id, store=store, check_physical=check_physical,
        )
        while True:
            if work >= work_limit or len(issues) >= findings_limit:
                return _assessment_page(
                    issues, state, actor_id=actor_id, store=store,
                    check_physical=check_physical, work=work,
                )
            remaining = work_limit - work
            if state["phase"] == "ready":
                query = DocumentVersion.objects.filter(processing_state=DocumentVersion.ProcessingState.READY)
                if state["position"]:
                    query = query.filter(id__gt=state["position"])
                rows = list(query.order_by("id")[:min(DATABASE_BATCH_SIZE, remaining)])
                if not rows:
                    state = {"v": 1, "phase": "current", "position": None}
                    continue
                for version in rows:
                    if work >= work_limit or len(issues) >= findings_limit:
                        return _assessment_page(
                            issues, state, actor_id=actor_id, store=store,
                            check_physical=check_physical, work=work,
                        )
                    if check_physical and work_limit - work < 1 + (2 * maximum_chunks):
                        if work == 0:
                            raise InventoryWorkLimitError(
                                "Work limit is too small for physical READY assessment"
                            )
                        return _assessment_page(
                            issues, state, actor_id=actor_id, store=store,
                            check_physical=check_physical, work=work,
                        )
                    work += 1
                    original = OriginalArtifact.objects.filter(document_version=version).first()
                    extracted = ExtractedTextArtifact.objects.filter(document_version=version).first()
                    if original is None:
                        issues.append(RecoveryIssue("ready_missing_original", str(version.pk)))
                    if extracted is None:
                        issues.append(RecoveryIssue("ready_missing_extracted", str(version.pk)))
                    if check_physical:
                        for kind, artifact in (("original", original), ("extracted", extracted)):
                            if artifact is None:
                                continue
                            valid, used = _bounded_artifact_valid(store, artifact, work_limit - work)
                            work += used
                            if not valid:
                                issues.append(RecoveryIssue(f"ready_invalid_{kind}", str(version.pk)))
                    state["position"] = str(version.pk)
                    if len(issues) >= findings_limit:
                        return _assessment_page(
                            issues, state, actor_id=actor_id, store=store,
                            check_physical=check_physical, work=work,
                        )
                continue
            query = Document.objects.exclude(current_version=None)
            if state["position"]:
                query = query.filter(id__gt=state["position"])
            rows = list(query.select_related("current_version").order_by("id")[:min(DATABASE_BATCH_SIZE, remaining)])
            if not rows:
                return _assessment_page(
                    issues, state, actor_id=actor_id, store=store,
                    check_physical=check_physical, work=work, complete=True,
                )
            for document in rows:
                if work >= work_limit or len(issues) >= findings_limit:
                    return _assessment_page(
                        issues, state, actor_id=actor_id, store=store,
                        check_physical=check_physical, work=work,
                    )
                work += 1
                state["position"] = str(document.pk)
                version = document.current_version
                if version.processing_state != DocumentVersion.ProcessingState.READY:
                    issues.append(RecoveryIssue("current_not_ready", str(document.pk)))
                if not OriginalArtifact.objects.filter(document_version=version).exists():
                    issues.append(RecoveryIssue("current_missing_original", str(document.pk)))
                if not ExtractedTextArtifact.objects.filter(document_version=version).exists():
                    issues.append(RecoveryIssue("current_missing_extracted", str(document.pk)))
                if len(issues) >= findings_limit:
                    return _assessment_page(
                        issues, state, actor_id=actor_id, store=store,
                        check_physical=check_physical, work=work,
                    )
    finally:
        if owns_store:
            store.close()


def _parse_datetime(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise InventoryCursorError("Inventory cursor position is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed


def _bounded_artifact_valid(store, artifact, remaining_work):
    maximum_bytes = settings.DOCUMENT_MAX_FILE_BYTES + 1
    expected_chunks = max(1, math.ceil(maximum_bytes / HASH_CHUNK_SIZE))
    if remaining_work < expected_chunks:
        return None, 0
    try:
        path = store.resolve(artifact.storage_key)
        digest = hashlib.sha256()
        size = chunks = 0
        with path.open("rb") as source:
            while chunk := source.read(HASH_CHUNK_SIZE):
                chunks += 1
                size += len(chunk)
                if size > settings.DOCUMENT_MAX_FILE_BYTES:
                    return False, chunks
                digest.update(chunk)
        return size == artifact.byte_length and digest.hexdigest() == artifact.sha256_digest, max(chunks, 1)
    except (ArtifactStorageError, OSError):
        return False, 1


def _page_result(issues, state, *, actor_id, store, work, complete=False):
    cursor = None if complete else _encode_cursor(state, actor_id=actor_id, store=store)
    return RecoveryInventoryPage(tuple(issues), cursor, complete, work)


def inventory_recovery_page(*, actor_id, store=None, now=None, findings_limit=100,
                            work_limit=DEFAULT_WORK_LIMIT, cursor=None):
    if (isinstance(findings_limit, bool) or not isinstance(findings_limit, int)
            or findings_limit < 1 or findings_limit > 1000):
        raise ValueError("Findings limit must be between 1 and 1000")
    if (isinstance(work_limit, bool) or not isinstance(work_limit, int)
            or work_limit < 1 or work_limit > MAX_WORK_LIMIT):
        raise InventoryWorkLimitError("Work limit must be between 1 and 10000")
    owns_store = store is None
    store = store or PrivateArtifactStore()
    now = now or timezone.now()
    issues = []
    work = 0
    try:
        state = _decode_cursor(cursor, actor_id=actor_id, store=store)
        while True:
            if len(issues) >= findings_limit or work >= work_limit:
                return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
            phase = state["phase"]
            remaining = work_limit - work
            if phase == "stale_jobs":
                query = ProcessingJob.objects.filter(
                    state=ProcessingJob.State.RUNNING, lease_expires_at__lte=now,
                )
                if state["position"]:
                    stamp = _parse_datetime(state["position"][0]); pk = state["position"][1]
                    query = query.filter(Q(lease_expires_at__gt=stamp) | Q(lease_expires_at=stamp, id__gt=pk))
                size = min(DATABASE_BATCH_SIZE, remaining)
                rows = list(query.order_by("lease_expires_at", "id").values_list("lease_expires_at", "id")[:size])
                work += len(rows)
                for stamp, pk in rows:
                    state["position"] = [stamp.isoformat(), str(pk)]
                    issues.append(RecoveryIssue("stale_job", str(pk)))
                    if len(issues) >= findings_limit:
                        return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if len(rows) == size and size == remaining:
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if len(rows) == size == DATABASE_BATCH_SIZE:
                    continue
                state.update({"phase": "originals", "position": None})
                continue
            if phase in {"originals", "extracted"}:
                model = OriginalArtifact if phase == "originals" else ExtractedTextArtifact
                query = model.objects.order_by("id")
                if state["position"]:
                    query = query.filter(id__gt=state["position"])
                maximum_chunks = math.ceil((settings.DOCUMENT_MAX_FILE_BYTES + 1) / HASH_CHUNK_SIZE)
                if remaining <= maximum_chunks:
                    if work == 0:
                        raise InventoryWorkLimitError("Work limit is too small for artifact validation")
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                size = min(DATABASE_BATCH_SIZE, remaining - maximum_chunks)
                rows = list(query.only("id", "storage_key", "byte_length", "sha256_digest", "document_version_id")[:size])
                work += len(rows)
                for artifact in rows:
                    valid, used = _bounded_artifact_valid(store, artifact, work_limit - work)
                    if valid is None:
                        return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                    work += used
                    state["position"] = str(artifact.pk)
                    if not valid:
                        issues.append(RecoveryIssue("invalid_artifact", str(artifact.document_version_id)))
                    if len(issues) >= findings_limit or work >= work_limit:
                        return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if len(rows) == size == DATABASE_BATCH_SIZE:
                    continue
                if len(rows) == size and size == remaining:
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                next_phase = "extracted" if phase == "originals" else "filesystem_originals"
                state.update({"phase": next_phase, "position": None, "fs": None})
                continue
            if phase == "filesystem_originals":
                fs = state["fs"] or {"mode": "root", "root_offset": 0, "root_digest": None}
                if remaining < DIRECTORY_ENTRY_CAP + 2:
                    if work == 0:
                        raise InventoryWorkLimitError("Work limit is too small for a directory snapshot")
                    state["fs"] = fs
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if fs["mode"] == "root":
                    snapshot = store.inventory_directory_snapshot(namespace="originals", entry_cap=DIRECTORY_ENTRY_CAP)
                    work += snapshot.work
                    if fs["root_digest"] is not None and fs["root_digest"] != snapshot.digest:
                        raise ArtifactInventoryChanged("Artifact inventory cursor is stale")
                    if fs["root_offset"] >= len(snapshot.names):
                        state.update({"phase": "filesystem_extracted", "position": None, "fs": None})
                        continue
                    fs = {"mode": "leaf", "directory": snapshot.names[fs["root_offset"]], "offset": 0,
                          "digest": None, "root_offset": fs["root_offset"] + 1, "root_digest": snapshot.digest}
                    state["fs"] = fs
                    continue
                shard = fs["directory"]
                snapshot = store.inventory_directory_snapshot(namespace="originals", directory=shard,
                                                                entry_cap=DIRECTORY_ENTRY_CAP)
                work += snapshot.work
                if fs["digest"] is not None and fs["digest"] != snapshot.digest:
                    raise ArtifactInventoryChanged("Artifact inventory cursor is stale")
                offset = fs["offset"]
                available = min(len(snapshot.names) - offset, work_limit - work, DATABASE_BATCH_SIZE)
                names = snapshot.names[offset:offset + max(available, 0)]
                keys = [f"originals/{shard}/{name}" for name in names]
                referenced = set(OriginalArtifact.objects.filter(storage_key__in=keys).values_list("storage_key", flat=True))
                referenced.update(ExtractedTextArtifact.objects.filter(storage_key__in=keys).values_list("storage_key", flat=True))
                work += len(keys)
                for key in keys:
                    offset += 1
                    fs.update({"offset": offset, "digest": snapshot.digest})
                    state["fs"] = fs
                    if key not in referenced:
                        issues.append(RecoveryIssue("orphan_artifact", key))
                    if len(issues) >= findings_limit or work >= work_limit:
                        return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if offset >= len(snapshot.names):
                    fs = {"mode": "root", "root_offset": fs["root_offset"], "root_digest": fs["root_digest"]}
                state["fs"] = fs
                continue
            if phase == "filesystem_extracted":
                fs = state["fs"] or {"mode": "root", "root_offset": 0, "root_digest": None}
                if remaining < DIRECTORY_ENTRY_CAP + 2:
                    if work == 0:
                        raise InventoryWorkLimitError("Work limit is too small for a directory snapshot")
                    state["fs"] = fs
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if fs["mode"] == "root":
                    snapshot = store.inventory_directory_snapshot(namespace="extracted", entry_cap=DIRECTORY_ENTRY_CAP)
                    work += snapshot.work
                    if fs["root_digest"] is not None and fs["root_digest"] != snapshot.digest:
                        raise ArtifactInventoryChanged("Artifact inventory cursor is stale")
                    if fs["root_offset"] >= len(snapshot.names):
                        state.update({"phase": "purge", "position": None, "fs": None})
                        continue
                    fs = {"mode": "leaf", "directory": snapshot.names[fs["root_offset"]], "offset": 0,
                          "digest": None, "root_offset": fs["root_offset"] + 1, "root_digest": snapshot.digest}
                    state["fs"] = fs
                    continue
                snapshot = store.inventory_directory_snapshot(namespace="extracted", directory=fs["directory"],
                                                                entry_cap=DIRECTORY_ENTRY_CAP)
                work += snapshot.work
                if fs["digest"] is not None and fs["digest"] != snapshot.digest:
                    raise ArtifactInventoryChanged("Artifact inventory cursor is stale")
                offset = fs["offset"]
                available = min(len(snapshot.names) - offset, work_limit - work, DATABASE_BATCH_SIZE)
                names = snapshot.names[offset:offset + max(available, 0)]
                keys = [f"extracted/{fs['directory']}/{name}" for name in names]
                referenced = set(OriginalArtifact.objects.filter(storage_key__in=keys).values_list("storage_key", flat=True))
                referenced.update(ExtractedTextArtifact.objects.filter(storage_key__in=keys).values_list("storage_key", flat=True))
                work += len(keys)
                for key in keys:
                    offset += 1; fs.update({"offset": offset, "digest": snapshot.digest}); state["fs"] = fs
                    if key not in referenced:
                        issues.append(RecoveryIssue("orphan_artifact", key))
                    if len(issues) >= findings_limit or work >= work_limit:
                        return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
                if offset >= len(snapshot.names):
                    fs = {"mode": "root", "root_offset": fs["root_offset"], "root_digest": fs["root_digest"]}
                state["fs"] = fs
                continue
            query = Document.objects.filter(
                visibility=Document.Visibility.DELETED, deleted_at__lte=now - timedelta(days=30),
            )
            if state["position"]:
                stamp = _parse_datetime(state["position"][0]); pk = state["position"][1]
                query = query.filter(Q(deleted_at__gt=stamp) | Q(deleted_at=stamp, id__gt=pk))
            size = min(DATABASE_BATCH_SIZE, remaining)
            rows = list(query.order_by("deleted_at", "id").values_list("deleted_at", "id")[:size])
            work += len(rows)
            for stamp, pk in rows:
                state["position"] = [stamp.isoformat(), str(pk)]
                issues.append(RecoveryIssue("purge_eligible", str(pk)))
                if len(issues) >= findings_limit:
                    return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
            if len(rows) == size == DATABASE_BATCH_SIZE:
                continue
            if len(rows) == size and size == remaining:
                return _page_result(issues, state, actor_id=actor_id, store=store, work=work)
            return _page_result(issues, state, actor_id=actor_id, store=store, work=work, complete=True)
    finally:
        if owns_store:
            store.close()
