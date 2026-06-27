"""Analysis application configuration."""

from django.apps import AppConfig


class AnalysisConfig(AppConfig):
    """Django app config for analysis."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "analysis"
