# Generated repair migration to merge parallel monitoring migration branches.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0005_departmentsession_session_department_session_and_more"),
        ("monitoring", "0007_blockedsite_created_at"),
    ]

    operations = []
