# monitoring/serializers.py

from pathlib import PurePath
from rest_framework import serializers
from .models import (
    Employee,
    ActivityLog,
    IdleTime,
    ProductiveAppUsage,
    Session,
    ScreenshotLog,
    BlockedWebsiteAttempt,
    Screenshot,
    ClientEvent,
)


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "dept",
            "role",
            "system_username",
        ]


class ActivityLogSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            'employee',
            'app_name',
            'window_title',
            'timestamp',
        ]

    def validate_app_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("App name is required.")
        return value[:250]


class IdleTimeSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = IdleTime
        fields = [
            'employee',
            'start_time',
            'end_time',
            'total_idle_sec',
        ]

    def validate(self, attrs):
        if attrs["end_time"] < attrs["start_time"]:
            raise serializers.ValidationError(
                "Idle end time must be after start time."
            )
        calculated = int(
            (attrs["end_time"] - attrs["start_time"]).total_seconds()
        )
        if attrs["total_idle_sec"] > calculated + 5:
            raise serializers.ValidationError(
                "Idle duration does not match the submitted time range."
            )
        return attrs


class ProductiveAppUsageSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProductiveAppUsage
        fields = [
            'employee',
            'app_name',
            'date',
            'total_time_sec',
        ]

    def validate_app_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("App name is required.")
        return value[:250]


class SessionSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Session
        fields = [
            'employee',
            'start_time',
            'end_time',
            'total_time_sec',
        ]


class ScreenshotLogSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ScreenshotLog
        fields = [
            'employee',
            'file_path',
            'timestamp',
        ]

    def validate_file_path(self, value):
        cleaned = value.strip().replace("\\", "/")
        path = PurePath(cleaned)
        if path.is_absolute() or ".." in path.parts:
            raise serializers.ValidationError(
                "Screenshot path must be a safe relative path."
            )
        if not cleaned.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            raise serializers.ValidationError(
                "Unsupported screenshot file extension."
            )
        return cleaned


class ScreenshotSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Screenshot
        fields = [
            "id",
            "employee",
            "timestamp",
            "image_path",
            "active_app",
        ]
        read_only_fields = ["timestamp"]

    def validate_image_path(self, value):
        cleaned = value.strip().replace("\\", "/")
        path = PurePath(cleaned)
        if path.is_absolute() or ".." in path.parts:
            raise serializers.ValidationError(
                "Screenshot path must be a safe relative path."
            )
        if not cleaned.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            raise serializers.ValidationError(
                "Unsupported screenshot file extension."
            )
        return cleaned

    def validate_active_app(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Active app is required.")
        return value[:255]


class BlockedWebsiteAttemptSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = BlockedWebsiteAttempt
        fields = [
            'employee',
            'website',
            'app_name',
            'window_title',
            'timestamp',
        ]


class ClientEventSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ClientEvent
        fields = [
            "id",
            "event_id",
            "idempotency_key",
            "event_type",
            "employee",
            "device_id",
            "payload",
            "status",
            "error_message",
            "received_at",
        ]
        read_only_fields = ["status", "error_message", "received_at"]


class HeartbeatSerializer(serializers.Serializer):
    """
    Not a model serializer — heartbeat just updates employee status.
    """
    employee_id   = serializers.IntegerField()
    status        = serializers.CharField(max_length=20)
    timestamp     = serializers.DateTimeField()
    agent_version = serializers.CharField(max_length=20)

    # Aliases for backwards compatibility with views.py
IdleEventSerializer = IdleTimeSerializer
ProductiveAppSerializer = ProductiveAppUsageSerializer