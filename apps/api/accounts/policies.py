from .models import User


KNOWN_ROLES = {choice.value for choice in User.ITRole}


def _active_user(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "it_role", None) in KNOWN_ROLES
    )


def _has_role(user, *roles):
    return _active_user(user) and user.it_role in roles


def can_manage_it_categories(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN)


def can_create_it_document(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR)


def can_revise_it_document(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR)


def can_publish_it_document(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR)


def can_archive_it_document(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR)


def can_view_it_document(user, *, published, archived):
    if _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR):
        return True
    return _has_role(user, User.ITRole.IT_MEMBER) and bool(published or archived)


def can_request_correction(user):
    return _has_role(user, User.ITRole.IT_MEMBER)


def can_review_corrections(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN, User.ITRole.IT_EDITOR)


def can_delete_it_document_permanently(user):
    return _has_role(user, User.ITRole.IT_DOC_ADMIN)


def can_access_private_resource(user, *, owner_id):
    return _active_user(user) and user.pk is not None and user.pk == owner_id


def can_access_private_web_document(user, *, owner_id):
    return can_access_private_resource(user, owner_id=owner_id)


def can_access_credential_vault(user, *, owner_id):
    return can_access_private_resource(user, owner_id=owner_id)


def can_invite_accounts(user):
    return _active_user(user) and bool(getattr(user, "is_app_admin", False))
