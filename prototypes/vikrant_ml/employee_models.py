from django.db import models


class EmployeeReport(models.Model):
    employee_id = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True)

    report_type = models.CharField(max_length=50, default="regular")

    productive_time_min = models.FloatField(null=True, blank=True)
    unproductive_time_min = models.FloatField(null=True, blank=True)
    idle_time_min = models.FloatField(null=True, blank=True)
    app_switches = models.FloatField(null=True, blank=True)
    deleted_files = models.FloatField(null=True, blank=True)

    focus_score = models.FloatField(null=True, blank=True)
    task_completion_rate = models.FloatField(null=True, blank=True)
    productive_ratio = models.FloatField(null=True, blank=True)

    productivity_prediction = models.CharField(max_length=50, null=True, blank=True)
    productivity_confidence = models.FloatField(null=True, blank=True)
    productivity_score = models.FloatField(null=True, blank=True)

    anomaly_detected = models.BooleanField(default=False)
    anomaly_score = models.FloatField(null=True, blank=True)

    risk_level = models.CharField(max_length=20, null=True, blank=True)
    risk_score = models.FloatField(null=True, blank=True)
    risk_factors = models.TextField(null=True, blank=True)

    suspicious_files = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

