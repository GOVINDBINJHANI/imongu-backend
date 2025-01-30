from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'notify/(?P<company_id>[\w-]+)/$', consumers.NotificationConsumer.as_asgi()),
]