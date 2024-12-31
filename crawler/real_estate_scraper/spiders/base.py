import scrapy
from real_estate_scraper.database import get_db
from models.error import Error
import traceback


class BaseSpider(scrapy.Spider):
    is_paginating = False
    total_pages = 0
    total_listings = 0
    visited_urls = []

    def handle_error(self, failure):
        db = next(get_db())
        error_data = Error(
            url=self.url,
            error_type="Spider",
            error_message=str(failure),
            error_traceback=traceback.format_exc(),
        )
        db.add(error_data)
        db.commit()
