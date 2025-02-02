from django.db import models
from common.models import TimestampedMixin
from bot.models import User


class Source(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    base_url = models.CharField(max_length=255, unique=True)
    scraper_config = models.TextField()


class Listing(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    url = models.CharField(unique=True)
    title = models.CharField(max_length=255)
    short_description = models.TextField(null=True)
    detail_description = models.TextField(null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_currency = models.CharField(max_length=3)
    status = models.CharField(max_length=255)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    city = models.CharField(max_length=255, null=True)
    municipality = models.CharField(max_length=255, null=True)
    micro_location = models.CharField(max_length=255, null=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True)
    seller = models.ForeignKey("Seller", on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.source.name} - {self.url}"


class RawData(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True)
    html = models.TextField()
    data = models.TextField()


class Property(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.OneToOneField(Listing, on_delete=models.CASCADE)
    property_type = models.CharField(max_length=255, null=True)
    building_type = models.CharField(max_length=255, null=True)
    size_m2 = models.FloatField(null=True)
    floor_number = models.CharField(max_length=255, null=True)
    total_floors = models.IntegerField(null=True)
    rooms = models.FloatField(null=True)
    property_state = models.CharField(max_length=255, null=True)


class Image(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    source_url = models.CharField(default="")
    url = models.CharField(default="")
    sequence_number = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["url", "listing"], name="unique_url_listing"
            )
        ]


class Seller(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    source_seller_id = models.CharField(max_length=255, null=True)
    name = models.CharField(max_length=255)
    seller_type = models.CharField(max_length=255)
    primary_phone = models.CharField(max_length=255, null=True)
    primary_email = models.CharField(max_length=255, null=True)
    website = models.CharField(max_length=255, null=True)
    agent = models.ForeignKey("Agent", on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.name} - {self.seller_type}"


class Agent(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    agent_id = models.CharField(max_length=255, null=True)
    business_site_address = models.CharField(max_length=255, null=True)
    company_manager = models.CharField(max_length=255, null=True)
    company_owners = models.CharField(max_length=255, null=True)
    company_type_id = models.CharField(max_length=255, null=True)
    company_type_name = models.CharField(max_length=255, null=True)
    email = models.CharField(max_length=255, null=True)
    formal_owners_full_name = models.CharField(max_length=255, null=True)
    hq_address = models.CharField(max_length=255, null=True)
    identification_number = models.CharField(max_length=255, null=True)
    insurance_contract_expiry_date = models.DateField(null=True)
    insurance_expiry = models.BooleanField(default=False)
    insurance_expiry_within_month = models.BooleanField(default=False)
    main_activity = models.CharField(max_length=255, null=True)
    name = models.CharField(max_length=255)
    owner_full_name = models.CharField(max_length=255, null=True)
    owner_national_number = models.CharField(max_length=255, null=True)
    registry_date = models.DateField(null=True)
    registry_number = models.CharField(max_length=255, null=True, db_index=True)
    registry_statement_date = models.DateField(null=True)
    registry_statement_number = models.CharField(max_length=255, null=True)
    representatives_full_name = models.CharField(max_length=255, null=True)
    tax_number = models.CharField(max_length=255, null=True)
    web_page = models.CharField(max_length=255, null=True)

    def __str__(self):
        return f"{self.name} - {self.seller_type}"


class ListingChange(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    raw_data = models.ForeignKey(RawData, on_delete=models.SET_NULL, null=True)
    change_type = models.CharField(max_length=255)
    field = models.CharField(max_length=255)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)
    changed_at = models.DateTimeField()


class Report(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    source_name = models.CharField(max_length=255, null=True)
    total_pages = models.IntegerField()
    total_listings = models.IntegerField()
    total_actual_listings = models.IntegerField(default=0)
    total_new_listings = models.IntegerField(default=0)
    total_changed_listings = models.IntegerField(default=0)
    item_scraped_count = models.IntegerField()
    item_dropped_count = models.IntegerField()
    response_error_count = models.IntegerField()
    elapsed_time_seconds = models.FloatField(default=0)


class Error(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    url = models.CharField(max_length=255, default="")
    error_type = models.CharField(max_length=255)
    error_message = models.TextField()
    error_traceback = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["url", "error_type", "error_message"],
                name="unique_error_constraint",
            )
        ]


class Queue(TimestampedMixin, models.Model):
    id = models.UUIDField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_sent = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "user"], name="unique_listing_and_user_queue"
            )
        ]

    def __str__(self):
        return " to ".join([self.listing.id, self.user.chat_id])
