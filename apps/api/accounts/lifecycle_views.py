from collections.abc import Mapping
from math import ceil

from django.db.models import ProtectedError
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_denied_event_best_effort

from .lifecycle import (
    InvalidLifecycleRequest, InvalidLifecycleState, LastActiveAdmin,
    deactivate_user, reactivate_user, request_deletion_review, update_user_roles, user_payload,
)
from .models import User
from .policies import can_invite_accounts


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


def _admin_or_error(request, target_id=None):
    user = request.user
    if not user or not user.is_authenticated or not user.is_active:
        record_denied_event_best_effort(action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED, actor_user_id=None, target_type=SecurityAuditEvent.TargetType.ACCOUNT, target_id=str(target_id) if target_id else None)
        return None, _error("authentication_required", "Authentication required", 401)
    if not can_invite_accounts(user):
        record_denied_event_best_effort(action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED, actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.ACCOUNT, target_id=str(target_id) if target_id else None)
        return None, _error("permission_denied", "Permission denied", 403)
    return user, None


def _mutation_response(call):
    try:
        value = call()
    except User.DoesNotExist:
        return _error("not_found", "Not found", 404)
    except InvalidLifecycleRequest:
        return _error("invalid_request", "Request is invalid", 400)
    except InvalidLifecycleState:
        return _error("invalid_state", "Account state does not allow this operation", 400)
    except LastActiveAdmin:
        return _error("last_active_admin", "At least one active App Admin is required", 409)
    return value


class UserListView(APIView):
    permission_classes = []

    def get(self, request):
        _, error = _admin_or_error(request)
        if error:
            return error
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            return _error("invalid_request", "Pagination is invalid", 400)
        if page < 1 or page_size < 1 or page_size > 100:
            return _error("invalid_request", "Pagination is invalid", 400)
        queryset = User.objects.order_by("id")
        count = queryset.count()
        start = (page - 1) * page_size
        users = [user_payload(user) for user in queryset[start:start + page_size]]
        return Response({"users": users, "pagination": {"page": page, "page_size": page_size, "count": count, "total_pages": ceil(count / page_size) if count else 0}})


@method_decorator(csrf_protect, name="dispatch")
class UserDetailView(APIView):
    permission_classes = []

    def get(self, request, user_id):
        _, error = _admin_or_error(request, user_id)
        if error:
            return error
        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return _error("not_found", "Not found", 404)
        return Response({"user": user_payload(target)})

    def patch(self, request, user_id):
        actor, error = _admin_or_error(request, user_id)
        if error:
            return error
        if not isinstance(request.data, Mapping):
            return _error("invalid_request", "Request is invalid", 400)
        result = _mutation_response(lambda: update_user_roles(actor=actor, target_id=user_id, changes=dict(request.data)))
        return result if isinstance(result, Response) else Response({"user": user_payload(result)})


class _LifecycleView(APIView):
    permission_classes = []
    operation = None

    @method_decorator(csrf_protect)
    def post(self, request, user_id):
        actor, error = _admin_or_error(request, user_id)
        if error:
            return error
        result = _mutation_response(lambda: self.operation(actor=actor, target_id=user_id))
        return result if isinstance(result, Response) else Response({"user": user_payload(result)})


class DeactivateUserView(_LifecycleView):
    operation = staticmethod(deactivate_user)


class ReactivateUserView(_LifecycleView):
    operation = staticmethod(reactivate_user)


class DeletionReviewView(APIView):
    permission_classes = []

    @method_decorator(csrf_protect)
    def post(self, request, user_id):
        actor, error = _admin_or_error(request, user_id)
        if error:
            return error
        if not isinstance(request.data, Mapping):
            return _error("invalid_request", "Request is invalid", 400)
        result = _mutation_response(lambda: request_deletion_review(actor=actor, target_id=user_id, reason_code=request.data.get("reason_code")))
        if isinstance(result, Response):
            return result
        return Response({"review": {"id": str(result.pk), "status": "pending_review"}}, status=202)
