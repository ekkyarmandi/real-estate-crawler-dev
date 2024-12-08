from django.db import models
from common.models import TimestampedMixin


class Listing(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    source_id = models.CharField(max_length=255)
    url = models.CharField(unique=True)
    title = models.CharField(max_length=255)
    short_description = models.TextField(null=True)
    detail_description = models.TextField(null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_currency = models.CharField(max_length=3)
    status = models.CharField(max_length=255)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    total_views = models.IntegerField()
    city = models.CharField(max_length=255)
    municipality = models.CharField(max_length=255)
    micro_location = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.source_id} - {self.url}"


class RawData(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True)
    reponse_time = models.FloatField(null=True)
    html = models.TextField()
    data = models.TextField()
    # source
    # total_pages
    # total_listings


class Property(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    property_type = models.CharField(max_length=255)
    building_type = models.CharField(max_length=255, null=True)
    size_m2 = models.FloatField()
    floor_number = models.IntegerField(null=True)
    total_floors = models.IntegerField(null=True)
    rooms = models.FloatField(null=True)
    property_state = models.CharField(max_length=255, null=True)

    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"


class Image(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    url = models.CharField()
    sequence_number = models.IntegerField()


class Source(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    base_url = models.CharField(max_length=255, unique=True)
    scraper_config = models.TextField()


class Seller(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True)
    source_seller_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    seller_type = models.CharField(max_length=255)
    primary_phone = models.CharField(max_length=255, null=True)
    primary_email = models.CharField(max_length=255, null=True)
    website = models.CharField(max_length=255, null=True)


class ListingChange(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    raw_data = models.ForeignKey(RawData, on_delete=models.SET_NULL, null=True)
    change_type = models.CharField(max_length=255)
    field = models.CharField(max_length=255)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)
    changed_at = models.DateTimeField()
