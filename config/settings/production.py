"""
Production settings for Math Facts.

Mounted at adderoaks.com/mathfacts/ via Nginx path-prefix proxy_pass (the
trailing slash strips '/mathfacts/' before forwarding, so Django sees '/' as
the URL). FORCE_SCRIPT_NAME tells Django to prepend '/mathfacts' when
reversing URLs and serving the script-name in templates.

Static files: nginx must declare
    location ^~ /mathfacts/static/ { alias /home/deploy/mathfacts/staticfiles/; }
to win over the adderoaks vhost's static-extension regex (see /workspace/repos/CLAUDE.md).
"""

from .base import *  # noqa: F401,F403
import dj_database_url
from decouple import config

DEBUG = False

# WhiteNoise serves hashed/compressed static files in production.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Path-prefix mount: /mathfacts/ on adderoaks.com
FORCE_SCRIPT_NAME = '/mathfacts'
STATIC_URL = '/mathfacts/static/'
SESSION_COOKIE_PATH = '/mathfacts/'
CSRF_COOKIE_PATH = '/mathfacts/'

# nginx terminates TLS and proxies to gunicorn over HTTP.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://adderoaks.com',
    cast=lambda v: [s.strip() for s in v.split(',')],
)

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Security — set *_SECURE=False in .env while running over plain HTTP before cert is issued.
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
