from pathlib import Path

from celery.schedules import crontab

from config.logging import build_logging
from config.settings.environment import (
    env_bool,
    env_int,
    env_int_list,
    env_proxy_networks,
    env_str,
    env_str_list,
    load_environment_file,
)

BASE_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BASE_DIR.parent

load_environment_file(REPOSITORY_ROOT / ".env")

API_VERSION = "1.0.0"
API_TITLE = "Tactiqo API"

SECRET_KEY = env_str("DJANGO_SECRET_KEY", default="")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_str_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

MAXIMUM_TRUSTED_PROXY_HOPS = 8

TRUSTED_PROXY_NETWORKS = env_proxy_networks("DJANGO_TRUSTED_PROXY_NETWORKS", default=[])

TRUSTED_PROXY_HOPS = env_int(
    "DJANGO_TRUSTED_PROXY_HOPS", default=0, minimum=0, maximum=MAXIMUM_TRUSTED_PROXY_HOPS
)

SIGN_IN_THROTTLE_RATE = env_str("DJANGO_SIGN_IN_THROTTLE_RATE", default="5/m")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.fixtures",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", default="tactiqo"),
        "USER": env_str("POSTGRES_USER", default="tactiqo"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", default=""),
        "HOST": env_str("POSTGRES_HOST", default="postgres"),
        "PORT": env_str("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env_str("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "tactiqo",
    },
}

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

SESSION_PURGE_EXPIRY_SECONDS = 3000

FIXTURE_SYNCHRONIZATION_PAST_DAYS = 2
FIXTURE_SYNCHRONIZATION_FUTURE_DAYS = 14

# The lease covers a run long enough that the previous 900 seconds could not,
# and stays below the 3600-second Redis visibility timeout after which Celery
# redelivers an unacknowledged task: a task redelivered under
# CELERY_TASK_ACKS_LATE therefore always finds the lease free rather than
# skipping itself as a duplicate. A run that still outlives the lease keeps its
# successor's lock intact, because the task releases a lease only on a match.
FIXTURE_SYNCHRONIZATION_LOCK_SECONDS = 1800

# A queued run stays valid until shortly before the next scheduled one, so a
# worker outage shorter than the six-hour interval delays a refresh instead of
# discarding it and leaving fixtures unrefreshed for twelve hours.
FIXTURE_SYNCHRONIZATION_EXPIRY_SECONDS = 21000

CELERY_BEAT_SCHEDULE = {
    "accounts-purge-expired-sessions": {
        "task": "accounts.purge_expired_sessions",
        "schedule": crontab(minute="15"),
        "options": {"expires": SESSION_PURGE_EXPIRY_SECONDS},
    },
    "fixtures-synchronize": {
        "task": "fixtures.synchronize_fixtures",
        "schedule": crontab(minute="5", hour="*/6"),
        "options": {"expires": FIXTURE_SYNCHRONIZATION_EXPIRY_SECONDS},
    },
}

SPORTMONKS_API_TOKEN = env_str("SPORTMONKS_API_TOKEN", default="")

SPORTMONKS_BASE_URL = env_str(
    "SPORTMONKS_BASE_URL", default="https://api.sportmonks.com/v3/football"
)

SPORTMONKS_LEAGUE_IDS = env_int_list("SPORTMONKS_LEAGUE_IDS", default=[8, 82, 301, 384, 564])

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

CELERY_TIMEZONE = TIME_ZONE

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", default="INFO").upper()

LOGGING_CONFIG = "config.logging.configure"

LOGGING = build_logging(LOG_LEVEL)
