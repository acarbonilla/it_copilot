from .authorization import _issue_test_authorization


def authorize_sensitive_operation_for_test(actor):
    """Restricted IC-021 test seam; production routes intentionally have no caller."""
    actor_id = getattr(actor, "pk", None)
    if not isinstance(actor_id, int) or actor_id <= 0:
        raise ValueError("A persisted test actor is required")
    return _issue_test_authorization(actor_id)
