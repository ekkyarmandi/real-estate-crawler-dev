# Generated by Django 5.1.3 on 2024-12-02 05:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0007_alter_seller_primary_email_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="seller",
            name="website",
            field=models.CharField(max_length=255, null=True),
        ),
    ]
