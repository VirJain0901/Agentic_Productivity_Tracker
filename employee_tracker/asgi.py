"""
ASGI config for employee_tracker project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter,URLRouter
from channels.auth import AuthMiddlewareStack
import monitoring.routing




os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_tracker.settings')

application = ProtocolTypeRouter({
    # Handles normal HTTP view endpoints
    "http": get_asgi_application(),
    
    # Handles persistent WebSocket connection streams
    "websocket": AuthMiddlewareStack(
        URLRouter(
            monitoring.routing.websocket_urlpatterns
        )
    ),
})
