import scrapy
from real_estate_scraper.database import get_db
from models.error import Error
import traceback


class BaseSpider(scrapy.Spider):
    is_paginating = False
    total_pages = 0
    total_listings = 0
    total_new_listings = 0
    total_changed_listings = 0
    visited_urls = []

    def handle_error(self, failure):
        db = next(get_db())
        url = failure.request.url
        error_data = Error(
            url=url,
            error_type="Spider",
            error_message=str(failure),
            error_traceback=traceback.format_exc(),
        )
        try:
            db.add(error_data)
            db.commit()
            db.close()
        except Exception as err:
            if "unique_error_constraint" not in str(err):
                print(err)
