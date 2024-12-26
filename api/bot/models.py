from django.db import models
from common.models import TimestampedMixin
import json

DEFAULT_SETTINGS = {
    "city": "Beograd",
    "price": "50000-150000",
    "size": "45-120",
    "rooms": "3.0",
}


class User(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    profile_url = models.CharField(max_length=255)
    settings = models.TextField(default=json.dumps(DEFAULT_SETTINGS))

    def __str__(self):
        return f"{self.username} - {self.name}"
