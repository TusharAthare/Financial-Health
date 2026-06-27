"""API URL configuration."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from core.views.v1.auth import LogoutView, RegisterView, TokenObtainPairView


def health_check(request) -> JsonResponse:
    """Return a simple health-check payload."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health-check/", health_check),
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("api/refresh-token/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/core/", include("core.urls")),
    path("api/statements/", include("statements.urls")),
    path("api/analysis/", include("analysis.urls")),
]
