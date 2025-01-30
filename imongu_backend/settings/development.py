""" To run the development server just comment the two app in INSTALLED_APPS in base.py
1. django_elasticsearch_dsl
2. django_elasticsearch_dsl_drf
"""

from .base import *
from decouple import config

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


DEBUG = True

# DATABASE
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "imongudbdev",
        "USER": "root",
        "PASSWORD": "shivam1234",
        "HOST": "localhost",
        "PORT": "3306",
    }
}

ES_PASSWORD = config("ES_PASSWORD")

# Elasticsearch configuration
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": "http://localhost:9200",
        "http_auth": ("elastic", ES_PASSWORD),
    }
}

# Elasticsearch client
from elasticsearch import Elasticsearch

client = Elasticsearch("http://localhost:9200", http_auth=("elastic", ES_PASSWORD))
