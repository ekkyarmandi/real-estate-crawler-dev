# Generated by Django 5.1.3 on 2024-12-26 23:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bot", "0002_alter_user_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="chat_id",
            field=models.CharField(default=-1, max_length=255, unique=True),
            preserve_default=False,
        ),
    ]