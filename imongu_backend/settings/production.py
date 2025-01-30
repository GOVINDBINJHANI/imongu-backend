from .base import *
from decouple import config

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "api.imongu.com", "0.0.0.0"]


DEBUG = True

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USERNAME"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": "3306",
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}


ES_PASSWORD = config("ES_PASSWORD")

# Elasticsearch configuration
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": "http://18.189.113.215:9200",
        "http_auth": ("elastic", ES_PASSWORD),
    }
}

# Elasticsearch client
from elasticsearch import Elasticsearch

client = Elasticsearch("http://18.189.113.215:9200", http_auth=("elastic", ES_PASSWORD))
