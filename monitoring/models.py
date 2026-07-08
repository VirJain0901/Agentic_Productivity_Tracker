from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import os

class Employee(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", on_delete=models.CASCADE, related_name="monitoring_employees",null=True,blank=True )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    dept = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    system_username = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Idle", "Idle"),
        ("Offline", "Offline")
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Offline"
    )

    last_seen = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return (
            f"{self.first_name} "
            f"{self.last_name} "
            f"({self.system_username})"
        )

class ProductiveAppUsage(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    app_name = models.CharField(max_length=250)
    date = models.DateField()
    total_time_sec = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "app_name", "date"],
                name="unique_daily_employee_app_usage",
            )
        ]
        indexes = [
            models.Index(fields=["employee", "date"], name="usage_emp_date_idx"),
            models.Index(fields=["app_name", "date"], name="usage_app_date_idx"),
        ]

    def __str__(self):
        return f"{self.employee} - {self.app_name} - {self.date}"


class IdleTime(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_idle_sec = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=["employee", "start_time"], name="idle_emp_start_idx"),
        ]


class DepartmentSession(models.Model):
    dept = models.CharField(max_length=100)
    session_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dept", "session_date"],
                name="unique_department_session_per_day"
            )
        ]

    def __str__(self):
        return f"{self.dept} - {self.session_date}"


class Session(models.Model):
    department_session = models.ForeignKey(DepartmentSession,on_delete=models.CASCADE,related_name="employee_sessions",null=True,blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    total_time_sec = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "start_time"], name="session_emp_start_idx"),
            models.Index(fields=["employee", "end_time"], name="session_emp_end_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(end_time__isnull=True),
                name="unique_active_session_per_employee"
            )
        ]

class ActivityLog(models.Model):

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE
    )

    app_name = models.CharField(max_length=255)

    window_title = models.TextField()

    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.employee} - {self.app_name}"


class BlockedWebsiteAttempt(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE
    )
    website = models.CharField(max_length=255)
    app_name = models.CharField(max_length=255)
    window_title = models.TextField()
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.employee} - {self.website}"


class ScreenshotLog(models.Model):
    employee = models.ForeignKey(Employee,on_delete=models.CASCADE)
    file_path = models.TextField()
    metadata_hash = models.CharField(max_length=32, blank=True, null=True, db_index=True)
    timestamp = models.DateTimeField( auto_now_add=True)

    def __str__(self):
        return (f"{self.employee} - " f"{self.timestamp}")
    
    def get_file_url(self):
        if not self.file_path:
            return ""    
           
        # Normalize backslashes (Windows) to forward slashes for URLs
        normalized_path = self.file_path.replace('\\', '/')
        parts = normalized_path.split('/')
        
        # Grab the last 3 pieces: 'YYYY-MM-DD', 'HH', and 'hash.png'
        if len(parts) >= 3:
            relative_url_path = "/".join(parts[-3:])
            
            # Returns: /media/screenshots/2026-06-26/15/d41d8cd98f...png
            return f"{settings.MEDIA_URL}screenshots/{relative_url_path}"
        return os.path.join(settings.MEDIA_URL, os.path.basename(self.file_path))



class BlockedSite(models.Model):
    url = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url


class Screenshot(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE) 
    timestamp = models.DateTimeField(auto_now_add=True)
    image_path = models.CharField(max_length=500)  # Path to stored file
    active_app = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "timestamp"], name="screenshot_emp_time_idx"),
            models.Index(fields=["active_app", "timestamp"], name="screenshot_app_time_idx"),
        ]
    
    def __str__(self):
        return f"Screenshot - {self.employee.system_username} - {self.timestamp}"


class ClientEvent(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        DUPLICATE = "duplicate", "Duplicate"
        REJECTED = "rejected", "Rejected"

    event_id = models.CharField(max_length=128, unique=True)
    idempotency_key = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=64)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACCEPTED)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "received_at"], name="clientevent_emp_time_idx"),
            models.Index(fields=["device_id", "received_at"], name="clientevent_dev_time_idx"),
            models.Index(fields=["event_type", "received_at"], name="clientevent_type_time_idx"),
        ]
    
    def __str__(self):
        return f"{self.event_type}:{self.event_id}"
    
class AgentHeartbeat(models.Model):
    tenant_id = models.CharField(max_length=128)
    device_id = models.CharField(max_length=128)
    hostname = models.CharField(max_length=100)
    policy_version = models.CharField(max_length=50)
    agent_version = models.CharField(max_length=20)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ("tenant_id", "device_id")

    def __str__(self):
        return f"{self.tenant_id} / {self.device_id} ({self.hostname})"

