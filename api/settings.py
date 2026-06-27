"""Financial Health API — Django settings."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
ENVIRONMENT = os.getenv("ENVIRONMENT", "LOCAL")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "core",
    "statements",
    "analysis",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "api.wsgi.application"
ASGI_APPLICATION = "api.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "financial_health"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

if ENVIRONMENT == "TESTING":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / os.getenv("MEDIA_ROOT", "media")

STATEMENT_MAX_UPLOAD_BYTES = int(
    os.getenv("STATEMENT_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)),
)
STATEMENT_ALLOWED_EXTENSIONS = frozenset(
    ext.strip().lower()
    for ext in os.getenv("STATEMENT_ALLOWED_EXTENSIONS", "csv,pdf,xls,xlsx").split(",")
    if ext.strip()
)
PDF_MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("PDF_MIN_TEXT_CHARS_PER_PAGE", "20"))
PDF_MIN_TOTAL_TEXT_CHARS = int(os.getenv("PDF_MIN_TOTAL_TEXT_CHARS", "50"))
XLSX_HEADER_SCAN_ROWS = int(os.getenv("XLSX_HEADER_SCAN_ROWS", "50"))
STATEMENT_DELETE_RAW_AFTER_PARSE = os.getenv(
    "STATEMENT_DELETE_RAW_AFTER_PARSE",
    "True",
).lower() in ("true", "1", "yes")
STATEMENT_RAW_RETENTION_SECONDS = int(
    os.getenv("STATEMENT_RAW_RETENTION_SECONDS", "0"),
)

MAX_STATEMENTS_PER_USER = int(os.getenv("MAX_STATEMENTS_PER_USER", "100"))
MAX_UPLOADS_PER_DAY = int(os.getenv("MAX_UPLOADS_PER_DAY", "20"))
EXPORT_JOB_RETENTION_HOURS = int(os.getenv("EXPORT_JOB_RETENTION_HOURS", "24"))

USER_CATEGORY_RULE_PRIORITY = int(os.getenv("USER_CATEGORY_RULE_PRIORITY", "10"))
RECURRING_MIN_OCCURRENCES = int(os.getenv("RECURRING_MIN_OCCURRENCES", "3"))
RECURRING_GAP_TOLERANCE_DAYS = int(os.getenv("RECURRING_GAP_TOLERANCE_DAYS", "5"))
RECURRING_MAX_AMOUNT_VARIANCE_PCT = float(
    os.getenv("RECURRING_MAX_AMOUNT_VARIANCE_PCT", "10.0"),
)
INSIGHT_LOW_SAVINGS_THRESHOLD_PCT = float(
    os.getenv("INSIGHT_LOW_SAVINGS_THRESHOLD_PCT", "10.0"),
)
INSIGHT_GOOD_SAVINGS_THRESHOLD_PCT = float(
    os.getenv("INSIGHT_GOOD_SAVINGS_THRESHOLD_PCT", "20.0"),
)
INSIGHT_HIGH_EMI_THRESHOLD_PCT = float(
    os.getenv("INSIGHT_HIGH_EMI_THRESHOLD_PCT", "40.0"),
)
INSIGHT_RISING_SPEND_THRESHOLD_PCT = float(
    os.getenv("INSIGHT_RISING_SPEND_THRESHOLD_PCT", "15.0"),
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "True").lower() in ("true", "1", "yes")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BATCH_SIZE = int(os.getenv("GEMINI_BATCH_SIZE", "20"))
GEMINI_MAX_BATCHES_PER_REQUEST = int(os.getenv("GEMINI_MAX_BATCHES_PER_REQUEST", "1"))
GEMINI_BATCH_PAUSE_SECONDS = float(os.getenv("GEMINI_BATCH_PAUSE_SECONDS", "0"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
GEMINI_RETRY_DELAY_SECONDS = float(os.getenv("GEMINI_RETRY_DELAY_SECONDS", "15"))
GEMINI_RULE_PRIORITY = int(os.getenv("GEMINI_RULE_PRIORITY", "200"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
# Estimated USD per 1M tokens (override per deployment / model pricing sheet).
GEMINI_COST_INPUT_PER_MILLION_USD = float(
    os.getenv("GEMINI_COST_INPUT_PER_MILLION_USD", "0.15"),
)
GEMINI_COST_OUTPUT_PER_MILLION_USD = float(
    os.getenv("GEMINI_COST_OUTPUT_PER_MILLION_USD", "0.60"),
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:4200,http://127.0.0.1:4200",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "cleanup-stale-raw-files": {
        "task": "analysis.tasks.cleanup_stale_raw_files_task",
        "schedule": 3600.0,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "api.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "api.throttling.ApiUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("API_RATE_LIMIT", "200/hour"),
        "upload": os.getenv("UPLOAD_RATE_LIMIT", "30/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Financial Health API",
    "DESCRIPTION": "Personal finance analyzer API",
    "VERSION": "0.1.0",
}

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "False").lower() in ("true", "1", "yes")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=ENVIRONMENT,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )

if OTEL_ENABLED:
    from opentelemetry import trace
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create({"service.name": "financial-health-api"})
    provider = TracerProvider(resource=resource)
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otel_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    DjangoInstrumentor().instrument()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "api.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
