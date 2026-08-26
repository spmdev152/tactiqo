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
    "apps.predictions",
    "apps.statistics",
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

# Predictions cover exactly the fixtures that exist, so the window is the
# fixture window rather than one of its own: a fixture the listing can show but
# the prediction run never read would offer a panel that is permanently empty.
# That is why the two windows are one pair of constants and not two.

# Five leagues over the fixture window are on the order of a hundred and fifty
# fixtures, read in one paginated request, so a run is far shorter than the
# fixture run this lease is sized against; the reasoning above applies
# unchanged, and the margin is spent on the fifty rows each fixture writes.
PREDICTION_SYNCHRONIZATION_LOCK_SECONDS = 1800

# Same six-hour cadence as the fixtures, so a queued run stays valid until
# shortly before its successor.
PREDICTION_SYNCHRONIZATION_EXPIRY_SECONDS = 21000

# One request per subscribed league, so a run is five calls and a handful of
# rows. The lease is sized for the request budget rather than the write.
PREDICTION_RELIABILITY_LOCK_SECONDS = 600

# The grades move over a season, not over a day, so the refresh is daily and a
# queued run stays valid for almost the whole interval.
PREDICTION_RELIABILITY_EXPIRY_SECONDS = 82800

# Statistics are read for matches that have already been played, so the window
# looks backwards only and is its own constant rather than the fixture pair: a
# full matchweek plus the midweek round either side of it, which is long enough
# that a run missed overnight still catches every result it would have written.
STATISTICS_SYNCHRONIZATION_PAST_DAYS = 5

# A backfill walks its range in chunks of this many days. The bound exists
# because the client refuses a read it cannot finish in forty pages of fifty
# fixtures, and five leagues produce on the order of two hundred fixtures a
# month, so a month-wide chunk stays an order of magnitude inside the ceiling
# while keeping the request count low.
STATISTICS_SYNCHRONIZATION_CHUNK_DAYS = 30

# Each chunk costs two paginated reads, the fixtures and their statistics, and a
# backfill can be given a range spanning two seasons. The lease is sized for that
# operator-run case rather than for the trailing window, and still sits below the
# 3600-second Redis visibility timeout after which Celery redelivers an
# unacknowledged task.
STATISTICS_SYNCHRONIZATION_LOCK_SECONDS = 3000

# Same six-hour cadence as the fixtures, so a queued run stays valid until
# shortly before its successor.
STATISTICS_SYNCHRONIZATION_EXPIRY_SECONDS = 21000

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
    "predictions-synchronize": {
        "task": "predictions.synchronize_predictions",
        "schedule": crontab(minute="35", hour="*/6"),
        "options": {"expires": PREDICTION_SYNCHRONIZATION_EXPIRY_SECONDS},
    },
    "predictions-synchronize-reliability": {
        "task": "predictions.synchronize_reliability",
        "schedule": crontab(minute="50", hour="3"),
        "options": {"expires": PREDICTION_RELIABILITY_EXPIRY_SECONDS},
    },
    "statistics-synchronize": {
        "task": "statistics.synchronize_statistics",
        "schedule": crontab(minute="20", hour="*/6"),
        "options": {"expires": STATISTICS_SYNCHRONIZATION_EXPIRY_SECONDS},
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
