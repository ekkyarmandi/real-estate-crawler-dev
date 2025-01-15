# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import re
import scrapy
from itemloaders.processors import TakeFirst, MapCompose


def as_float(value):
    if isinstance(value, str) and re.match(r"\d", value):
        value = value.replace(".", "")
        value = value.replace(",", ".")
        return float(value) if value is not None else None
    elif isinstance(value, int):
        return float(value)
    return None


def as_int(value):
    if isinstance(value, str) and re.match(r"\d", value):
        value = value.replace(".", "")
        value = value.replace(",", ".")
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
