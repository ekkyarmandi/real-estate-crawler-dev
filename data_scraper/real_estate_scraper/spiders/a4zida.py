from datetime import datetime
import scrapy
import math
import re
import uuid
import jmespath
import json

from real_estate_scraper.func import raw_json_formatter


class A4zidaSpider(scrapy.Spider):
    name = "4zida"
    allowed_domains = ["www.4zida.rs"]
    start_urls = [
        "https://www.4zida.rs/prodaja-stanova/beograd",
    ]
    is_paginating = False
    item_per_page = 0

    def parse(self, response):
        # find property urls
        urls = response.css("div:has(button):has(a) > a:has(p)::attr(href)").getall()
        urls = list(dict.fromkeys((urls)))
        for url in urls:
            yield response.follow(response.urljoin(url), callback=self.parse_detail)
        # find total properties listed in the page, then create pagination
        # if not self.is_paginating:
        #     self.is_paginating = True
        #     self.item_per_page = len(urls)
        #     total_counts = 0
        #     result = response.css("div > strong:contains(oglasa)::Text").re("[0-9.]+")
        #     if result:
        #         total_counts = result[0].replace(".", "")
        #         total_counts = int(total_counts)
        #     # create pagination
        #     total_pages = math.ceil(total_counts/self.item_per_page)
        #     for i in range(2, total_pages + 1):
        #         yield response.follow(f"https://www.4zida.rs/prodaja-stanova/beograd?strana={i}")

    def parse_detail(self, response):
        # find property data
        data = self.find_property_data(response)
        lonlat = self.find_longitude_latitude(response)
        property_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        images = self.get_images(data)
        yield {
            "property_id": property_id,
            "source_id": data.get("id"),
            "title": data.get("title"),
            "short_description": data.get("humanReadableDescription"),
            "detail_description": data.get("desc"),
            "price": data.get("price"),
            "price_currency": "EUR",  # TODO: find in HTML
            "status": "active",
            "first_seen_at": now,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
            "valid_from": None,  # COMMENT: not sure which data point to look
            "valid_to": None,  # COMMENT: not sure which data point to look
            "total_views": None,
            "url": response.url,
            "raw_data": {
                "property_data": data,
                "geolocation_data": lonlat,
            },
            ## additional data
            "property": {
                "property_type": data.get("type"),
                "bulding_type": data.get("category"),
                "size_m2": data.get("m2"),
                "floor_number": data.get("redactedFloor"),
                "total_floors": data.get("redactedTotalFloors"),
                "rooms": None,  # TODO: find in HTML
                "property_state": data.get("state"),
                "created_at": now,
                "updated_at": now,
            },
            "address": {
                "id": str(uuid.uuid4()),
                "city": jmespath.search("placeMetaData[0].title", data),
                "municipality": jmespath.search("placeMetaData[1].title", data),
                "micro_location": jmespath.search("placeMetaData[2].title", data),
                "latitude": lonlat.get("latitude"),
                "longitude": lonlat.get("longitude"),
                "created_at": now,
                "updated_at": now,
            },
            "source": {
                "id": str(uuid.uuid4()),
                "name": "4zida.rs",
                "website": "www.4zida.rs",
            },
            "seller": {
                "id": str(uuid.uuid4()),
                "source_seller_id": jmespath.search("author.id", data),
                "name": jmespath.search("author.fullName", data),
                "seller_type": "agency" if data.get("advertiserType") else "other",
                "primary_phone": jmespath.search("author.phones[0].national", data),
                "primary_email": jmespath.search("author.agency.email", data),
                "created_at": now,
                "updated_at": now,
            },
            "images": images,
        }

    def find_property_data(self, response):
        script = response.css("script:contains('superIndividual')::Text").get()
        try:
            text = re.search(r"self.__next_f.push\(\[(.*?)\]\)", script).group(1)
            text = re.sub(r'\\"', '"', text)
            text = re.sub(r"\\n", "\n", text)
            text = text.replace("null", "None")
            text = text.replace("false", "False")
            text = text.replace("true", "True")
            return eval(text[3:-1])
        except:
            return None

    def find_longitude_latitude(self, response):
        script = response.css("script:contains('longitude')::Text").get()
        try:
            text = re.search(r"self.__next_f.push\(\[(.*?)\]\)", script).group(1)
            text = re.sub(r'\\"', '"', text)
            text = re.search(
                r'"latitude":[0-9.]+\s*,\s*"longitude":[0-9.]+', text
            ).group()
            return eval("{" + text + "}")
        except:
            return None

    def get_images(self, data):
        images = []
        property_images = data.get("images", [])
        for img in property_images:
            if "adDetails" in img:
                ad_images = img.get("adDetails", {})
                ad_jpegs = {0: None}
                for key, value in ad_images.items():
                    if "jpeg" in key:
                        try:
                            resolution = re.search(r"(\d+)+x\d+", key).group(1)
                            resolution = int(resolution)
                            ad_jpegs.update({resolution: value})
                        except:
                            pass
                max_res = max(ad_jpegs.keys())
                images.append(ad_jpegs.get(max_res))
        return images
