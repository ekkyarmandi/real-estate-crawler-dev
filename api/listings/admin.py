from django.contrib import admin
from listings import models


@admin.register(models.Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_id",
        "created_at",
        "updated_at",
        "first_seen_at",
        "last_seen_at",
        "url",
        "title",
        "short_description",
        "price",
        "price_currency",
        "status",
        "valid_from",
        "valid_to",
        "total_views",
        "city",
        "municipality",
        "micro_location",
        "latitude",
        "longitude",
    )
