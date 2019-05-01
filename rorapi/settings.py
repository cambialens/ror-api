"""
Django settings for rorapi project.

Generated by 'django-admin startproject' using Django 2.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
import sentry_sdk

from dotenv import load_dotenv
from elasticsearch_dsl import connections
from requests_aws4auth import AWS4Auth
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN', None),
    integrations=[DjangoIntegration()]
)

# load ENV variables from container environment
# see https://github.com/phusion/baseimage-docker#envvar_dumps
# nginx doesn't pass through most env variables
load_dotenv(dotenv_path='/etc/container_environment')

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '0y0zn=hnz99$+c6lejml@chch54s2y2@-z##i$pstn62doft_g'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'coreapi',
    'django_prometheus',
    'rorapi',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'rorapi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'rorapi.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = []


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

ELASTIC_HOST = os.environ.get('ELASTIC_HOST', 'elasticsearch')
ELASTIC_PASSWORD = os.environ.get('ELASTIC_PASSWORD', 'changeme')

# use AWS4Auth for AWS Elasticsearch unless running locally via docker
if ELASTIC_HOST != 'elasticsearch':
    http_auth = AWS4Auth(os.environ.get('AWS_ACCESS_KEY_ID', None), os.environ.get('AWS_SECRET_ACCESS_KEY', None), os.environ.get('AWS_REGION', None), 'es')
else:
    http_auth = ('elastic', ELASTIC_PASSWORD)

ES = {
    'HOSTS': [{'host': os.environ.get('ELASTIC_HOST', 'localhost'),
               'port': os.environ.get('ELASTIC_PORT', '9200')}],
    'TIMEOUT': 60,
    'INDEX': 'org-id-grid',
    'INDEX_TEMPLATE': os.path.join(BASE_DIR, 'rorapi', 'index_template.json'),
    'BATCH_SIZE': 20,
    'HTTP_AUTH': http_auth
}

connections.create_connection(
    hosts=['{}:{}'.format(h['host'], h['port']) for h in ES['HOSTS']],
    timeout=ES['TIMEOUT'],
    http_auth=ES['HTTP_AUTH']
)

GRID = {
    'VERSION': '2019-02-17',
    'URL': 'https://digitalscience.figshare.com/ndownloader/files/14399291'
}

GRID['DIR'] = os.path.join(BASE_DIR, 'rorapi', 'data',
                           'grid-{}'.format(GRID['VERSION']))
GRID['ZIP_PATH'] = os.path.join(GRID['DIR'], 'grid.zip')
GRID['JSON_PATH'] = os.path.join(GRID['DIR'], 'grid.json')
GRID['ROR_PATH'] = os.path.join(GRID['DIR'], 'ror_dataset.json')

ROR_API = {
    'PAGE_SIZE': 20,
    'ID_PREFIX': 'https://ror.org/'
}
