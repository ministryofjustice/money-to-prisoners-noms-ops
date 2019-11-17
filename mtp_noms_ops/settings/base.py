from functools import partial
import os
from os.path import abspath, dirname, join
import sys
from urllib.parse import urljoin

BASE_DIR = dirname(dirname(abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

get_project_dir = partial(join, BASE_DIR)

APP = 'noms-ops'
ENVIRONMENT = os.environ.get('ENV', 'local')
APP_BUILD_DATE = os.environ.get('APP_BUILD_DATE')
APP_GIT_COMMIT = os.environ.get('APP_GIT_COMMIT')
MOJ_INTERNAL_SITE = True

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
SECRET_KEY = 'CHANGE_ME'
ALLOWED_HOSTS = []

START_PAGE_URL = os.environ.get('START_PAGE_URL', 'https://www.gov.uk/send-prisoner-money')
CASHBOOK_URL = (
    f'https://{os.environ["PUBLIC_CASHBOOK_HOST"]}'
    if os.environ.get('PUBLIC_CASHBOOK_HOST')
    else 'http://localhost:8001'
)
BANK_ADMIN_URL = (
    f'https://{os.environ["PUBLIC_BANK_ADMIN_HOST"]}'
    if os.environ.get('PUBLIC_BANK_ADMIN_HOST')
    else 'http://localhost:8002'
)
NOMS_OPS_URL = (
    f'https://{os.environ["PUBLIC_NOMS_OPS_HOST"]}'
    if os.environ.get('PUBLIC_NOMS_OPS_HOST')
    else 'http://localhost:8003'
)
SEND_MONEY_URL = (
    f'https://{os.environ["PUBLIC_SEND_MONEY_HOST"]}'
    if os.environ.get('PUBLIC_SEND_MONEY_HOST')
    else 'http://localhost:8004'
)
SITE_URL = NOMS_OPS_URL

# Application definition
INSTALLED_APPS = (
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.contenttypes',
    'django.contrib.auth',
)
PROJECT_APPS = (
    'anymail',
    'mtp_common',
    'widget_tweaks',
    'prisoner_location_admin',
    'security',
    'zendesk_tickets',
    'settings',
)
INSTALLED_APPS += PROJECT_APPS


WSGI_APPLICATION = 'mtp_noms_ops.wsgi.application'
ROOT_URLCONF = 'mtp_noms_ops.urls'
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'mtp_common.cp_migration.middleware.CloudPlatformMigrationMiddleware',
    'django.middleware.common.CommonMiddleware',
    'mtp_common.auth.csrf.CsrfViewMiddleware',
    'mtp_common.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'mtp_noms_ops.utils.UserPermissionMiddleware',
    'mtp_common.analytics.ReferrerPolicyMiddleware',
)

HEALTHCHECKS = []
AUTODISCOVER_HEALTHCHECKS = True

# security tightening
# some overridden in prod/docker settings where SSL is ensured
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = False
CSRF_FAILURE_VIEW = 'mtp_common.auth.csrf.csrf_failure'


# Data stores
DATABASES = {}
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'mtp',
    }
}


# Internationalization
LANGUAGE_CODE = 'en-gb'
LANGUAGES = (
    ('en-gb', 'English'),
    ('cy', 'Cymraeg'),
)
LOCALE_PATHS = (get_project_dir('translations'),)
TIME_ZONE = 'Europe/London'
USE_I18N = True
USE_L10N = True
USE_TZ = True
FORMAT_MODULE_PATH = ['mtp_noms_ops.settings.formats']


# Static files (CSS, JavaScript, Images)
STATIC_ROOT = 'static'
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    get_project_dir('assets'),
    get_project_dir('assets-static'),
]
PUBLIC_STATIC_URL = urljoin(SEND_MONEY_URL, STATIC_URL)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            get_project_dir('templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'mtp_common.context_processors.analytics',
                'mtp_common.context_processors.app_environment',
                'mtp_noms_ops.utils.govuk_localisation',
                'mtp_noms_ops.utils.external_breadcrumbs',
                'mtp_noms_ops.apps.security.context_processors.common',
                'mtp_noms_ops.apps.security.context_processors.initial_params',
                'mtp_noms_ops.apps.security.context_processors.prison_choice_available',
            ],
        },
    },
]

# logging settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s [%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
        'elk': {
            '()': 'mtp_common.logging.ELKFormatter'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if ENVIRONMENT == 'local' else 'elk',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console'],
    },
    'loggers': {
        'django.security.DisallowedHost': {
            'handlers': ['null'],
            'propagate': False,
        },
        'mtp': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

# sentry exception handling
if os.environ.get('SENTRY_DSN'):
    INSTALLED_APPS = ('raven.contrib.django.raven_compat',) + INSTALLED_APPS
    RAVEN_CONFIG = {
        'dsn': os.environ['SENTRY_DSN'],
        'release': APP_GIT_COMMIT or 'unknown',
    }
    LOGGING['handlers']['sentry'] = {
        'level': 'ERROR',
        'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler'
    }
    LOGGING['root']['handlers'].append('sentry')
    LOGGING['loggers']['mtp']['handlers'].append('sentry')

TEST_RUNNER = 'mtp_common.test_utils.runner.TestRunner'

# authentication
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
AUTHENTICATION_BACKENDS = (
    'mtp_common.auth.backends.MojBackend',
)


# control the time a session exists for; should match api's access token expiry
SESSION_COOKIE_AGE = 60 * 60  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True


API_CLIENT_ID = 'noms-ops'
API_CLIENT_SECRET = os.environ.get('API_CLIENT_SECRET', 'noms-ops')
API_URL = os.environ.get('API_URL', 'http://localhost:8000')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'root'
LOGOUT_URL = 'logout'

OAUTHLIB_INSECURE_TRANSPORT = True

ANALYTICS_REQUIRED = os.environ.get('ANALYTICS_REQUIRED', 'True') == 'True'
GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID', None)

ZENDESK_BASE_URL = 'https://ministryofjustice.zendesk.com'
ZENDESK_API_USERNAME = os.environ.get('ZENDESK_API_USERNAME', '')
ZENDESK_API_TOKEN = os.environ.get('ZENDESK_API_TOKEN', '')
ZENDESK_REQUESTER_ID = os.environ.get('ZENDESK_REQUESTER_ID', '')
ZENDESK_GROUP_ID = 26417927
ZENDESK_CUSTOM_FIELDS = {
    'referer': 26047167,
    'username': 29241738,
    'user_agent': 23791776,
    'contact_email': 30769508,
}

REQUEST_PAGE_SIZE = 500
UPLOAD_REQUEST_PAGE_SIZE = 3000
MAX_CREDITS_TO_DOWNLOAD = 2000
MAX_CREDITS_TO_EMAIL = 20000

EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'
ANYMAIL = {
    'MAILGUN_API_KEY': os.environ.get('MAILGUN_ACCESS_KEY', ''),
    'MAILGUN_SENDER_DOMAIN': os.environ.get('MAILGUN_SERVER_NAME', ''),
    'SEND_DEFAULTS': {
        'tags': [APP, ENVIRONMENT],
    },
}
MAILGUN_FROM_ADDRESS = os.environ.get('MAILGUN_FROM_ADDRESS', '')
if MAILGUN_FROM_ADDRESS:
    DEFAULT_FROM_EMAIL = MAILGUN_FROM_ADDRESS

LOCATION_UPLOADER_USERNAME = os.environ.get('LOCATION_UPLOADER_USERNAME', 'prisoner-location-admin')
LOCATION_UPLOADER_PASSWORD = os.environ.get('LOCATION_UPLOADER_PASSWORD', 'prisoner-location-admin')

ASYNC_LOCATION_UPLOAD = os.environ.get('ASYNC_LOCATION_UPLOAD', 'True') == 'True'
SHOW_LANGUAGE_SWITCH = os.environ.get('SHOW_LANGUAGE_SWITCH', 'False') == 'True'

NOMIS_API_BASE_URL = os.environ.get('NOMIS_API_BASE_URL', '')
NOMIS_API_CLIENT_TOKEN = os.environ.get('NOMIS_API_CLIENT_TOKEN', '')
NOMIS_API_PRIVATE_KEY = os.environ.get('NOMIS_API_PRIVATE_KEY', '').encode('utf8').decode('unicode_escape')

NOMIS_ELITE_CLIENT_ID = os.environ.get('NOMIS_ELITE_CLIENT_ID', '')
NOMIS_ELITE_CLIENT_SECRET = os.environ.get('NOMIS_ELITE_CLIENT_SECRET', '')
NOMIS_ELITE_BASE_URL = os.environ.get('NOMIS_ELITE_BASE_URL', '')

TOKEN_RETRIEVAL_USERNAME = os.environ.get('TOKEN_RETRIEVAL_USERNAME', '_token_retrieval')
TOKEN_RETRIEVAL_PASSWORD = os.environ.get('TOKEN_RETRIEVAL_PASSWORD', '_token_retrieval')

CLOUD_PLATFORM_MIGRATION_MODE = os.environ.get('CLOUD_PLATFORM_MIGRATION_MODE', '')
CLOUD_PLATFORM_MIGRATION_URL = os.environ.get('CLOUD_PLATFORM_MIGRATION_URL', '')

try:
    from .local import *  # noqa
except ImportError:
    pass
