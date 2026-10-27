from django.db import DatabaseError, connections
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response({"error": {"code": "database_unavailable", "message": "Service temporarily unavailable"}}, status=503)
        return Response({"status": "ok"}, status=200)
