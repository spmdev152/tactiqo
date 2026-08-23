from config.logging import deployed_log_level
from config.settings.base import *
from config.settings.environment import env_str, require_env_str, require_env_str_list

SECRET_KEY = require_env_str("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = require_env_str_list("DJANGO_ALLOWED_HOSTS")

DATABASES = {
    "default": {
        **DATABASES["default"],
        "NAME": require_env_str("POSTGRES_DB"),
        "USER": require_env_str("POSTGRES_USER"),
        "PASSWORD": require_env_str("POSTGRES_PASSWORD"),
        "HOST": require_env_str("POSTGRES_HOST"),
    },
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = [
    f"https://*{host}" if host.startswith(".") else f"https://{host}" for host in ALLOWED_HOSTS
]

X_FRAME_OPTIONS = "DENY"

LOG_LEVEL = deployed_log_level(env_str("DJANGO_LOG_LEVEL", default="INFO").upper())

LOGGING = build_logging(LOG_LEVEL, serialize=True)
