from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # This creates the endpoint: ws://127.0.0.1:8000/ws/status/
    re_path(r'ws/status/$', consumers.TrackingConsumer.as_asgi()),
]