from django.contrib import admin
from .employee_models import EmployeeReport


@admin.register(EmployeeReport)
class EmployeeReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee_id",
        "timestamp",
        "report_type",
        "productivity_prediction",
        "risk_level",
        "risk_score",
        "anomaly_detected",
        "suspicious_files",
        "created_at",
    )
    list_filter = ("risk_level", "report_type", "anomaly_detected")
    search_fields = ("employee_id", "risk_level", "productivity_prediction")
    ordering = ("-created_at",)

