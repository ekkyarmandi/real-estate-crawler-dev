# Generated by Django 5.1.3 on 2024-12-17 15:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="report",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
