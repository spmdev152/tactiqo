from django.core.management.utils import get_random_secret_key

from config.settings.base import *
from config.settings.environment import env_bool, env_str, env_str_list

SECRET_KEY = env_str("DJANGO_SECRET_KEY", default=get_random_secret_key())
DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = env_str_list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "api", "[::1]"]
)

CELERY_TASK_EAGER_PROPAGATES = True

LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", default="DEBUG").upper()

LOGGING = build_logging(LOG_LEVEL, colorize=True, diagnose=True)
