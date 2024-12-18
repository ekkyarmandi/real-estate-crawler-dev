# Generated by Django 5.1.3 on 2024-12-17 15:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0002_alter_report_created_at"),
    ]

    operations = [
        migrations.RenameField(
            model_name="report",
            old_name="item_error_count",
            new_name="response_error_count",
        ),
        migrations.AddField(
            model_name="report",
            name="elapsed_time_seconds",
            field=models.FloatField(default=0),
        ),
    ]