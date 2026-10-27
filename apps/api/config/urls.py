from django.urls import path

from health.views import HealthView

urlpatterns = [path("api/v1/health", HealthView.as_view(), name="health")]
handler404 = "config.errors.structured_not_found"
