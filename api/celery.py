"""Celery application configuration."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

app = Celery("financial_health")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
