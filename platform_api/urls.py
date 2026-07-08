from django.urls import path

from . import views


urlpatterns = [
     path("health/", views.health_view, name="platform-v1-health"),
    path("sync/events/", views.activity_sync_view, name="platform-v1-sync-events"),
]