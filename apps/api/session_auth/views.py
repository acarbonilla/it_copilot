from collections.abc import Mapping

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.response import Response
from rest_framework.views import APIView


def identity_payload(user):
    return {
        "id": user.pk,
        "email": user.email,
        "is_app_admin": user.is_app_admin,
        "it_role": user.it_role,
    }


def active_authenticated_user(request):
    user = request.user
    if user and user.is_authenticated and user.is_active:
        return user
    return None


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request._request)}, status=200)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not isinstance(request.data, Mapping):
            return Response({"error": {"code": "invalid_request", "message": "Email and password are required"}}, status=400)

        email = request.data.get("email")
        password = request.data.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            return Response({"error": {"code": "invalid_request", "message": "Email and password are required"}}, status=400)

        user = authenticate(request=request._request, email=email, password=password)
        if user is None or not user.is_active:
            return Response({"error": {"code": "invalid_credentials", "message": "Invalid email or password"}}, status=401)

        login(request._request, user)
        return Response({"user": identity_payload(user)}, status=200)


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = []

    def post(self, request):
        if active_authenticated_user(request) is None:
            return Response({"error": {"code": "authentication_required", "message": "Authentication required"}}, status=401)
        logout(request._request)
        return Response(status=204)


class MeView(APIView):
    permission_classes = []

    def get(self, request):
        user = active_authenticated_user(request)
        if user is None:
            return Response({"error": {"code": "authentication_required", "message": "Authentication required"}}, status=401)
        return Response({"user": identity_payload(user)}, status=200)
