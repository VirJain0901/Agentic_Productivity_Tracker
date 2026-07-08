import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count, Min, Sum


def merge_duplicate_app_usage(apps, schema_editor):
    ProductiveAppUsage = apps.get_model("monitoring", "ProductiveAppUsage")
    duplicates = (
        ProductiveAppUsage.objects.values("employee_id", "app_name", "date")
        .annotate(row_count=Count("id"), total_seconds=Sum("total_time_sec"), keep_id=Min("id"))
        .filter(row_count__gt=1)
    )
    for duplicate in duplicates:
        queryset = ProductiveAppUsage.objects.filter(
            employee_id=duplicate["employee_id"],
            app_name=duplicate["app_name"],
            date=duplicate["date"],
        )
        queryset.filter(id=duplicate["keep_id"]).update(total_time_sec=duplicate["total_seconds"])
        queryset.exclude(id=duplicate["keep_id"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0003_screenshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productiveappusage",
            name="total_time_sec",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="session",
            name="end_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="session",
            name="total_time_sec",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(merge_duplicate_app_usage, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="productiveappusage",
            constraint=models.UniqueConstraint(
                fields=("employee", "app_name", "date"),
                name="unique_daily_employee_app_usage",
            ),
        ),
        migrations.AddIndex(
            model_name="productiveappusage",
            index=models.Index(fields=["employee", "date"], name="usage_emp_date_idx"),
        ),
        migrations.AddIndex(
            model_name="productiveappusage",
            index=models.Index(fields=["app_name", "date"], name="usage_app_date_idx"),
        ),
        migrations.AddIndex(
            model_name="idletime",
            index=models.Index(fields=["employee", "start_time"], name="idle_emp_start_idx"),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["employee", "start_time"], name="session_emp_start_idx"),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["employee", "end_time"], name="session_emp_end_idx"),
        ),
        migrations.AddIndex(
            model_name="screenshot",
            index=models.Index(fields=["employee", "timestamp"], name="screenshot_emp_time_idx"),
        ),
        migrations.AddIndex(
            model_name="screenshot",
            index=models.Index(fields=["active_app", "timestamp"], name="screenshot_app_time_idx"),
        ),
        migrations.CreateModel(
            name="ClientEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(max_length=128, unique=True)),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("event_type", models.CharField(max_length=64)),
                ("device_id", models.CharField(blank=True, max_length=128)),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("accepted", "Accepted"),
                            ("duplicate", "Duplicate"),
                            ("rejected", "Rejected"),
                        ],
                        default="accepted",
                        max_length=16,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="monitoring.employee"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="clientevent",
            index=models.Index(fields=["employee", "received_at"], name="clientevent_emp_time_idx"),
        ),
        migrations.AddIndex(
            model_name="clientevent",
            index=models.Index(fields=["device_id", "received_at"], name="clientevent_dev_time_idx"),
        ),
        migrations.AddIndex(
            model_name="clientevent",
            index=models.Index(fields=["event_type", "received_at"], name="clientevent_type_time_idx"),
        ),
    ]
