from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.models import Employee, AgentHeartbeat

class Command(BaseCommand):
    help = "Mark employees offline if heartbeat is old."

    def handle(self, *args, **kwargs):
        threshold = timezone.now() - timedelta(minutes=2)

        Employee.objects.filter(
            last_seen__lt=threshold,
            status="Active"
        ).update(status="Offline")

        self.stdout.write(self.style.SUCCESS("Employee statuses updated."))