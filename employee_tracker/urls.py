"""
URL configuration for employee_tracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from monitoring import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/blocklist/", views.blocklist),
    path("api/monitoring/policies/", views.monitoring_policies),
    path("api/health/", views.health),
    path('api/activity-log/', views.activity_log),
    path('api/idle-events/', views.idle_event),
    path('api/session/start/', views.session_start),
    path('api/session/end/', views.session_end),
    path('api/screenshot/', views.screenshot_metadata),
    path('api/activity-sync/', views.activity_sync),
    path("api/monitoring/heartbeat/", views.heartbeat, name="heartbeat"),
    path('api/v1/', include('platform_api.urls')),
    
    #JWT AUthentication ENdpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


