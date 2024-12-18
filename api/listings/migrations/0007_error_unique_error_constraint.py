# Generated by Django 5.1.3 on 2024-12-18 14:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0006_image_unique_url_listing"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="error",
            constraint=models.UniqueConstraint(
                fields=("url", "error_type", "error_message"),
                name="unique_error_constraint",
            ),
        ),
    ]
