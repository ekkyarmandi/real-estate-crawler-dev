# Generated by Django 5.1.3 on 2024-12-24 10:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0010_report_source_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="seller",
            name="source_seller_id",
            field=models.CharField(max_length=255, null=True),
        ),
    ]