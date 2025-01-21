# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import re
import scrapy
from itemloaders.processors import TakeFirst, MapCompose

from real_estate_scraper.func import str_to_price


def as_float(value):
    if isinstance(value, str) and re.match(r"\d", value):
        value = value.replace(".", "")
        value = value.replace(",", ".")
        value = value.replace("+", "")
        value = value.replace("m²", "")
        return float(value) if value is not None else None
    elif isinstance(value, int):
        return float(value)
    return None


def as_int(value):
    if isinstance(value, str) and re.match(r"\d", value):
        value = value.replace(".", "")
        value = value.replace(",", ".")
        value = value.replace("+", "")
        return int(value) if value is not None else None
    return None


class PropertyItem(scrapy.Item):
    property_type = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    building_type = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    size_m2 = scrapy.Field(
        input_processor=MapCompose(as_float),
        output_processor=TakeFirst(),
    )
    floor_number = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    total_floors = scrapy.Field(
        input_processor=MapCompose(as_int),
        output_processor=TakeFirst(),
    )
    rooms = scrapy.Field(
        input_processor=MapCompose(as_float),
        output_processor=TakeFirst(),
    )
    property_state = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )


class ListingItem(scrapy.Item):
    source_id = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    title = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    description = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=lambda x: "\n".join(x).strip() if x else None,
    )
    price = scrapy.Field(
        input_processor=MapCompose(str_to_price),
        output_processor=TakeFirst(),
    )

class AddressItem(scrapy.Item):
    city = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    municipality = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    micro_location = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    latitude = scrapy.Field(
        input_processor=MapCompose(as_float),
        output_processor=TakeFirst(),
    )
    longitude = scrapy.Field(
        input_processor=MapCompose(as_float),
        output_processor=TakeFirst(),
    )
