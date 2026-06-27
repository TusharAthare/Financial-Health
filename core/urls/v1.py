"""Core API v1 URL routes."""

from django.urls import path

from core.views.v1.data_privacy import AuditLogListView, DeleteMyDataView
from core.views.v1.me import MeView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("me/data/", DeleteMyDataView.as_view(), name="delete-my-data"),
    path("audit/", AuditLogListView.as_view(), name="audit-log"),
]
