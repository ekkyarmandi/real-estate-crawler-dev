# Generated by Django 5.1.3 on 2025-01-19 13:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0020_alter_property_size_m2"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="registry_number",
            field=models.CharField(db_index=True, max_length=255, null=True),
        ),
    ]
