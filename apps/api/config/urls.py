from django.urls import path

from accounts.invitation_views import ActivationView, InvitationCreateView
from health.views import HealthView
from session_auth.views import CsrfView, LoginView, LogoutView, MeView

urlpatterns = [
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/auth/csrf", CsrfView.as_view(), name="auth-csrf"),
    path("api/v1/auth/login", LoginView.as_view(), name="auth-login"),
    path("api/v1/auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("api/v1/auth/me", MeView.as_view(), name="auth-me"),
    path("api/v1/auth/activate", ActivationView.as_view(), name="auth-activate"),
    path("api/v1/users/invitations", InvitationCreateView.as_view(), name="user-invitations"),
]
handler404 = "config.errors.structured_not_found"
