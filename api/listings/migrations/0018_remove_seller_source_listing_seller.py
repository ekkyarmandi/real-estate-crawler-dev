# Generated by Django 5.1.3 on 2025-01-10 11:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0017_remove_listing_source_id_listing_source"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="seller",
            name="source",
        ),
        migrations.AddField(
            model_name="listing",
            name="seller",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="listings.seller",
            ),
        ),
    ]
