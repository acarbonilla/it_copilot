from django.core.exceptions import ValidationError
from django.db import models


ACTION_VALUES = (
    "auth.login_success",
    "auth.login_denied",
    "account.invite_created",
    "account.invite_revoked",
    "account.invite_reissued",
    "account.activation_succeeded",
    "account.activation_denied",
    "account.deactivated",
    "account.reactivated",
    "account.role_changed",
    "account.deletion_review_requested",
    "authorization.denied",
    "document.created",
    "document.metadata_updated",
    "document.archived",
    "document.restored",
    "document.deleted",
    "document.upload_created",
)
TARGET_TYPE_VALUES = ("account", "account_invitation", "authentication", "it_document", "private_resource")
OUTCOME_VALUES = ("success", "denied", "failure")


class SecurityAuditEvent(models.Model):
    class Action(models.TextChoices):
        AUTH_LOGIN_SUCCESS = "auth.login_success", "Authentication login succeeded"
        AUTH_LOGIN_DENIED = "auth.login_denied", "Authentication login denied"
        ACCOUNT_INVITE_CREATED = "account.invite_created", "Account invitation created"
        ACCOUNT_INVITE_REVOKED = "account.invite_revoked", "Account invitation revoked"
        ACCOUNT_INVITE_REISSUED = "account.invite_reissued", "Account invitation reissued"
        ACCOUNT_ACTIVATION_SUCCEEDED = "account.activation_succeeded", "Account activation succeeded"
        ACCOUNT_ACTIVATION_DENIED = "account.activation_denied", "Account activation denied"
        ACCOUNT_DEACTIVATED = "account.deactivated", "Account deactivated"
        ACCOUNT_REACTIVATED = "account.reactivated", "Account reactivated"
        ACCOUNT_ROLE_CHANGED = "account.role_changed", "Account role changed"
        ACCOUNT_DELETION_REVIEW_REQUESTED = "account.deletion_review_requested", "Account deletion review requested"
        AUTHORIZATION_DENIED = "authorization.denied", "Authorization denied"
        DOCUMENT_CREATED = "document.created", "Document created"
        DOCUMENT_METADATA_UPDATED = "document.metadata_updated", "Document metadata updated"
        DOCUMENT_ARCHIVED = "document.archived", "Document archived"
        DOCUMENT_RESTORED = "document.restored", "Document restored"
        DOCUMENT_DELETED = "document.deleted", "Document deleted"
        DOCUMENT_UPLOAD_CREATED = "document.upload_created", "Document upload created"

    class TargetType(models.TextChoices):
        ACCOUNT = "account", "Account"
        ACCOUNT_INVITATION = "account_invitation", "Account invitation"
        AUTHENTICATION = "authentication", "Authentication"
        IT_DOCUMENT = "it_document", "IT document"
        PRIVATE_RESOURCE = "private_resource", "Private resource"

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        DENIED = "denied", "Denied"
        FAILURE = "failure", "Failure"

    action = models.CharField(max_length=40, choices=Action.choices)
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    target_type = models.CharField(max_length=32, choices=TargetType.choices)
    target_id = models.CharField(max_length=128, null=True, blank=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    occurred_at = models.DateTimeField(auto_now_add=True, editable=False)
    request_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=ACTION_VALUES),
                name="audit_action_known",
            ),
            models.CheckConstraint(
                condition=models.Q(target_type__in=TARGET_TYPE_VALUES),
                name="audit_target_type_known",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=OUTCOME_VALUES),
                name="audit_outcome_known",
            ),
            models.CheckConstraint(
                condition=models.Q(actor_user_id__isnull=True) | models.Q(actor_user_id__gt=0),
                name="audit_actor_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("action", "occurred_at"), name="audit_action_time_idx"),
            models.Index(fields=("actor_user_id", "occurred_at"), name="audit_actor_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Security audit events are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Security audit events cannot be deleted through the model")
