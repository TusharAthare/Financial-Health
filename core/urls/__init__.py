"""Core API URL routes."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls.v1")),
]
