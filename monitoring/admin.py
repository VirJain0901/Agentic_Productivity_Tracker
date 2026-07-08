# monitoring/admin.py

import os
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Employee,
    ProductiveAppUsage,
    IdleTime,
    Session,
    ActivityLog,
    BlockedWebsiteAttempt,
    ScreenshotLog,
    Screenshot,
    BlockedSite,
    ClientEvent,
)


# ---------------- Employee ----------------

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):

    list_display = (
        "first_name",
        "last_name",
        "system_username",
        "status",
        "last_seen",
    )

    search_fields = (
        "first_name",
        "last_name",
        "system_username",
    )

    list_filter = (
        "status",
    )


# ---------------- Idle Time ----------------

@admin.register(IdleTime)
class IdleTimeAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "start_time",
        "end_time",
        "total_idle_sec",
    )

    list_filter = (
        "start_time",
    )

    ordering = (
        "-start_time",
    )


# ---------------- Productive App Usage ----------------

@admin.register(ProductiveAppUsage)
class ProductiveAppUsageAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "app_name",
        "date",
        "total_time_sec",
    )

    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "employee__system_username",
        "app_name",
    )

    list_filter = (
        "date",
        "app_name",
    )

    ordering = (
        "-date",
    )


# ---------------- Session ----------------

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "start_time",
        "end_time",
        "total_time_sec",
    )

    list_filter = (
        "start_time",
    )

    ordering = (
        "-start_time",
    )

    readonly_fields = (
        "total_time_sec",
    )


# ---------------- Activity Log ----------------

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "app_name",
        "window_title",
        "timestamp",
    )

    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "employee__system_username",
        "app_name",
        "window_title",
    )

    list_filter = (
        "app_name",
        "timestamp",
    )

    ordering = (
        "-timestamp",
    )

    readonly_fields = (
        "timestamp",
    )


# ---------------- Blocked Website Attempts ----------------

@admin.register(BlockedWebsiteAttempt)
class BlockedWebsiteAttemptAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "website",
        "app_name",
        "timestamp",
    )

    search_fields = (
        "employee__system_username",
        "employee__first_name",
        "employee__last_name",
        "website",
        "app_name",
    )

    list_filter = (
        "website",
        "timestamp",
    )

    ordering = (
        "-timestamp",
    )

    readonly_fields = (
        "timestamp",
    )


# ---------------- Screenshot Log ----------------

@admin.register(ScreenshotLog)
class ScreenshotLogAdmin(admin.ModelAdmin):

    list_display = (
        "employee",
        "timestamp",
        "screenshot_link",
    )

    search_fields = (
        "employee__system_username",
        "employee__first_name",
        "employee__last_name",
    )

    list_filter = (
        "timestamp",
    )

    ordering = (
        "-timestamp",
    )

    readonly_fields = (
        "timestamp",
    )

    def screenshot_link(self, obj):
        if obj.file_path:
            return format_html(
                '<a href="/media/{}" target="_blank">View Screenshot</a>',
                os.path.basename(obj.file_path)
            )
        return "No Image"

    screenshot_link.short_description = "Screenshot"


# ---------------- Screenshot (with preview) ----------------

@admin.register(Screenshot)
class ScreenshotAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "employee",
        "active_app",
        "timestamp",
        "preview_thumbnail",
    )

    fields = (
        "employee",
        "active_app",
        "image_path",
        "preview_details",
    )

    readonly_fields = (
        "preview_details",
    )

    def _safe_media_url(self, obj):
        if not obj.image_path:
            return None
        raw_path = obj.image_path.strip().replace("\\", "/")
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            return None
        media_root = Path(settings.MEDIA_ROOT).resolve()
        candidate = (media_root / relative).resolve()
        try:
            candidate.relative_to(media_root)
        except ValueError:
            return None
        if not candidate.exists() or not candidate.is_file():
            return None
        return f"{settings.MEDIA_URL.rstrip('/')}/{relative.as_posix()}"

    @admin.display(description="Thumbnail Preview")
    def preview_thumbnail(self, obj):
        media_url = self._safe_media_url(obj)
        if not media_url:
            return "No Image File"
        return format_html(
            '<img src="{}" width="80" '
            'style="object-fit:contain;border-radius:4px;" '
            'alt="screenshot preview">',
            media_url,
        )

    @admin.display(description="Live Preview Screen")
    def preview_details(self, obj):
        media_url = self._safe_media_url(obj)
        if not media_url:
            return "File path unavailable or outside media storage"
        return format_html(
            '<img src="{}" width="450" '
            'style="max-width:100%;border:2px solid #333;border-radius:6px;" '
            'alt="screenshot preview">',
            media_url,
        )


# ---------------- Blocked Site ----------------

@admin.register(BlockedSite)
class BlockedSiteAdmin(admin.ModelAdmin):

    list_display = (
        "url",
        "created_at",
    )

    search_fields = (
        "url",
    )

    ordering = (
        "-created_at",
    )


# ---------------- Client Event ----------------

@admin.register(ClientEvent)
class ClientEventAdmin(admin.ModelAdmin):

    list_display = (
        "event_id",
        "event_type",
        "employee",
        "device_id",
        "status",
        "received_at",
    )

    list_filter = (
        "event_type",
        "status",
        "received_at",
    )

    search_fields = (
        "event_id",
        "idempotency_key",
        "device_id",
        "employee__email",
        "employee__system_username",
    )

    readonly_fields = (
        "event_id",
        "idempotency_key",
        "event_type",
        "employee",
        "device_id",
        "payload",
        "status",
        "error_message",
        "received_at",
    )