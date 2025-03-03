# Generated by Django 5.1.3 on 2024-12-27 23:51

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bot", "0003_user_chat_id"),
        ("listings", "0011_alter_seller_source_seller_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Queue",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("is_sent", models.BooleanField(default=False)),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="listings.listing",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bot.user"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
