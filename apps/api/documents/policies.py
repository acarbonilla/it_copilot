from dataclasses import dataclass
from enum import Enum

from accounts.models import User

from .models import Document


class DocumentCapability(str, Enum):
    OPERATIONAL_METADATA = "operational_metadata"
    VIEW_METADATA = "view_metadata"
    CREATE = "create"
    EDIT_METADATA = "edit_metadata"
    VIEW_CONTENT = "view_content"
    DOWNLOAD = "download"
    PROCESS = "process"
    ARCHIVE = "archive"
    RESTORE = "restore"
    DELETE = "delete"


CONTENT_CAPABILITIES = frozenset(
    {
        DocumentCapability.VIEW_CONTENT,
        DocumentCapability.DOWNLOAD,
        DocumentCapability.PROCESS,
    }
)
OWNER_CAPABILITIES = frozenset(
    {
        DocumentCapability.VIEW_METADATA,
        DocumentCapability.CREATE,
        DocumentCapability.EDIT_METADATA,
        *CONTENT_CAPABILITIES,
        DocumentCapability.ARCHIVE,
        DocumentCapability.RESTORE,
        DocumentCapability.DELETE,
    }
)


@dataclass(frozen=True)
class DocumentAuthorization:
    allowed: bool
    reason_code: str


def is_active_identity(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "lifecycle_state", None) == User.LifecycleState.ACTIVE
        and getattr(user, "it_role", None) in {choice.value for choice in User.ITRole}
    )


def authorize_document(user, capability, *, document=None):
    try:
        capability = DocumentCapability(capability)
    except ValueError:
        return DocumentAuthorization(False, "unknown_capability")

    if not is_active_identity(user):
        return DocumentAuthorization(False, "inactive_or_anonymous")

    if capability == DocumentCapability.OPERATIONAL_METADATA:
        return DocumentAuthorization(bool(user.is_app_admin), "app_admin_required")

    if capability == DocumentCapability.CREATE:
        allowed = user.it_role in {User.ITRole.IT_MEMBER, User.ITRole.IT_EDITOR, User.ITRole.IT_DOC_ADMIN}
        return DocumentAuthorization(allowed, "it_role_required")

    if document is None or document.visibility == Document.Visibility.DELETED:
        return DocumentAuthorization(False, "document_unavailable")

    if user.it_role == User.ITRole.IT_DOC_ADMIN:
        return DocumentAuthorization(True, "it_doc_admin")

    if user.it_role in {User.ITRole.IT_MEMBER, User.ITRole.IT_EDITOR} and user.pk == document.owner_id:
        return DocumentAuthorization(capability in OWNER_CAPABILITIES, "owner")

    return DocumentAuthorization(False, "not_owner")


def visible_documents(user, queryset=None, *, include_archived=True):
    queryset = queryset if queryset is not None else Document.objects.all()
    if not is_active_identity(user):
        return queryset.none()
    queryset = queryset.exclude(visibility=Document.Visibility.DELETED)
    if not include_archived:
        queryset = queryset.filter(visibility=Document.Visibility.ACTIVE)
    if user.it_role == User.ITRole.IT_DOC_ADMIN:
        return queryset
    if user.it_role in {User.ITRole.IT_MEMBER, User.ITRole.IT_EDITOR}:
        return queryset.filter(owner_id=user.pk)
    return queryset.none()
