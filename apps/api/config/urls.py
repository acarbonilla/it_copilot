from django.urls import path

from accounts.invitation_views import ActivationView, InvitationCreateView
from accounts.lifecycle_views import DeactivateUserView, DeletionReviewView, ReactivateUserView, UserDetailView, UserListView
from health.views import HealthView
from documents.views import (DocumentArchiveView, DocumentCollectionView, DocumentDeleteView, DocumentDetailView,
                             DocumentDownloadView, DocumentRestoreView, DocumentRetryView, DocumentStatusView)
from session_auth.views import CsrfView, LoginView, LogoutView, MeView
from copilot.views import ConversationCollectionView, ConversationDetailView, ConversationMessageView
from vault.views import (VaultCredentialCollectionView, VaultCredentialDetailView, VaultCredentialRevealView,
                         VaultCredentialRestoreView, VaultDeletedCredentialCollectionView, VaultGrantRevokeView,
                         VaultReauthenticationView)

urlpatterns = [
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/auth/csrf", CsrfView.as_view(), name="auth-csrf"),
    path("api/v1/auth/login", LoginView.as_view(), name="auth-login"),
    path("api/v1/auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("api/v1/auth/me", MeView.as_view(), name="auth-me"),
    path("api/v1/auth/activate", ActivationView.as_view(), name="auth-activate"),
    path("api/v1/users/invitations", InvitationCreateView.as_view(), name="user-invitations"),
    path("api/v1/users", UserListView.as_view(), name="user-list"),
    path("api/v1/users/<int:user_id>", UserDetailView.as_view(), name="user-detail"),
    path("api/v1/users/<int:user_id>/deactivate", DeactivateUserView.as_view(), name="user-deactivate"),
    path("api/v1/users/<int:user_id>/reactivate", ReactivateUserView.as_view(), name="user-reactivate"),
    path("api/v1/users/<int:user_id>/deletion-reviews", DeletionReviewView.as_view(), name="user-deletion-review"),
    path("api/v1/documents", DocumentCollectionView.as_view(), name="document-list"),
    path("api/v1/documents/<uuid:document_id>", DocumentDetailView.as_view(), name="document-detail"),
    path("api/v1/documents/<uuid:document_id>/status", DocumentStatusView.as_view(), name="document-status"),
    path("api/v1/documents/<uuid:document_id>/download", DocumentDownloadView.as_view(), name="document-download"),
    path("api/v1/documents/<uuid:document_id>/archive", DocumentArchiveView.as_view(), name="document-archive"),
    path("api/v1/documents/<uuid:document_id>/restore", DocumentRestoreView.as_view(), name="document-restore"),
    path("api/v1/documents/<uuid:document_id>/delete", DocumentDeleteView.as_view(), name="document-delete"),
    path("api/v1/documents/<uuid:document_id>/retry", DocumentRetryView.as_view(), name="document-retry"),
    path("api/v1/copilot/conversations", ConversationCollectionView.as_view(), name="copilot-conversation-list"),
    path("api/v1/copilot/conversations/<uuid:conversation_id>", ConversationDetailView.as_view(), name="copilot-conversation-detail"),
    path("api/v1/copilot/conversations/<uuid:conversation_id>/messages", ConversationMessageView.as_view(), name="copilot-conversation-messages"),
    path("api/v1/vault/credentials", VaultCredentialCollectionView.as_view(), name="vault-credential-list"),
    path("api/v1/vault/deleted-credentials", VaultDeletedCredentialCollectionView.as_view(),
         name="vault-deleted-credential-list"),
    path("api/v1/vault/reauthenticate", VaultReauthenticationView.as_view(), name="vault-reauthenticate"),
    path("api/v1/vault/grants/revoke", VaultGrantRevokeView.as_view(), name="vault-grant-revoke"),
    path("api/v1/vault/credentials/<uuid:credential_id>", VaultCredentialDetailView.as_view(), name="vault-credential-detail"),
    path("api/v1/vault/credentials/<uuid:credential_id>/reveal", VaultCredentialRevealView.as_view(), name="vault-credential-reveal"),
    path("api/v1/vault/credentials/<uuid:credential_id>/restore", VaultCredentialRestoreView.as_view(), name="vault-credential-restore"),
]
handler404 = "config.errors.structured_not_found"
