"""Statements application configuration."""

from django.apps import AppConfig


class StatementsConfig(AppConfig):
    """Django app config for statements."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "statements"
