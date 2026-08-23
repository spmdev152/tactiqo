from django.core.management.utils import get_random_secret_key

from config.settings.base import *
from config.settings.environment import env_str

SECRET_KEY = env_str("DJANGO_SECRET_KEY", default=get_random_secret_key())
DEBUG = False
ALLOWED_HOSTS = ["testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tactiqo-test",
    },
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
