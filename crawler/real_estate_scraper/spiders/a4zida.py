from datetime import datetime
import scrapy
import math
import re
import uuid
import jmespath
import traceback

from real_estate_scraper.database import get_db
from models.error import Error


class A4zidaSpider(scrapy.Spider):
    name = "4zida"
    allowed_domains = ["www.4zida.rs"]
    start_urls = [
        "https://www.4zida.rs/prodaja-stanova/beograd",
    ]
    is_paginating = False
    total_listings = 0

    def parse(self, response):
        # find property urls
        urls = response.css("div:has(button):has(a) > a:has(p)::attr(href)").getall()
        urls = list(dict.fromkeys((urls)))
        for url in urls:
            yield response.follow(
                response.urljoin(url),
                callback=self.parse_detail,
            )

        # find total properties listed in the page, then create pagination
        item_per_page = 0
        if not self.is_paginating:
            self.is_paginating = True
            item_per_page = len(urls)
            total_counts = 0
            result = response.css("div > strong:contains(oglasa)::Text").re("[0-9.]+")
            if result:
                total_counts = result[0].replace(".", "")
                total_counts = int(total_counts)
                self.total_listings = total_counts
            # create pagination
            total_pages = math.ceil(total_counts / item_per_page)
            for i in range(2, total_pages + 1):
                next_url = response.url.split("?")[0] + "?strana=" + str(i)
                yield response.follow(next_url)

    def parse_detail(self, response):
        try:
            elapsed_time = response.meta.get("download_latency")
            # find property data
            data = self.find_property_data(response)
            lonlat = self.find_longitude_latitude(response)
            images = self.get_images(data)
            # assign data
            phonenumber = jmespath.search("author.phones[0].national", data)
            seller_name = jmespath.search("author.fullName", data)
            # missing value
            incomplete_pn = response.css("button::text").re_first("^0[0-9 ]+")
            descriptions = response.css(
                "main > section div[test-data=rich-text-description] ::Text"
            ).getall()
            descriptions = list(map(str.strip, descriptions))
            # find address
            address = response.css("h1 + div span::text").get()
            city = jmespath.search("placeMetaData[0].title", data)
            municipality = jmespath.search("placeMetaData[1].title", data)
            micro_location = jmespath.search("placeMetaData[2].title", data)
            x, y, z = None, None, None
            if address:
                address = address.split(",")
                address = list(map(str.strip, address))
                if len(address) > 2:
                    z, y, x = address[:3]
            page = dict(
                title=response.css("h1 ::Text").get(),
                price=response.css("p[test-data=ad-price] ::Text").re_first(
                    r"[0-9.,]+"
                ),
                descriptions="\n\n".join(descriptions),
                property=dict(
                    size_m2=response.css(
                        "strong:contains('m²'),strong:contains('m2')"
                    ).re_first(r"[0-9.,]+"),
                    rooms=response.css(
                        "strong:contains('rooms'),strong:contains('sobe')"
                    ).re_first(r"[0-9.,]+"),
                    floor_number=response.css("strong:contains('sprata')").re_first(
                        r"([0-9.,]+)/"
                    ),
                    total_floors=response.css("strong:contains('sprata')").re_first(
                        r"/([0-9.,]+)"
                    ),
                ),
                seller=dict(
                    name=response.css(
                        "section[test-data=author-info] span::text"
                    ).get(),
                    phonenumber=response.css(
                        f"script:contains('{incomplete_pn}')::text"
                    ).re_first(r"\d{3}\s+\d{7}"),
                ),
                address=dict(
                    city=z,
                    municipality=y,
                    micro_location=x,
                ),
            )
            yield {
                "listing_id": str(uuid.uuid4()),
                "elapsed_time": elapsed_time,
                "source_id": data.get("id"),
                "title": data.get("title", page["title"]),
                "short_description": data.get("humanReadableDescription"),
                "detail_description": data.get("desc", page["descriptions"]),
                "price": data.get("price", page["price"]),
                "price_currency": "EUR",  # TODO: find in HTML
                "status": "active",
                "valid_from": None,  # COMMENT: not sure which data point to look
                "valid_to": None,  # COMMENT: not sure which data point to look
                "total_views": 0,
                "url": response.url,
                "raw_data": {
                    "html": response.text,
                    "data": {
                        "property_data": data,
                        "geolocation_data": lonlat,
                    },
                },
                ## additional data
                "property": {
                    "property_type": data.get("type"),
                    "building_type": data.get("category"),
                    "size_m2": data.get("m2", page["property"]["size_m2"]),
                    "floor_number": data.get(
                        "redactedFloor", page["property"]["floor_number"]
                    ),
                    "total_floors": data.get(
                        "redactedTotalFloors", page["property"]["total_floors"]
                    ),
                    "rooms": page["property"]["rooms"],  # TODO: find in HTML
                    "property_state": data.get("state"),
                },
                "address": {
                    "city": city if city else page["address"]["city"],
                    "municipality": (
                        municipality
                        if municipality
                        else page["address"]["municipality"]
                    ),
                    "micro_location": (
                        micro_location
                        if micro_location
                        else page["address"]["micro_location"]
                    ),
                    "latitude": lonlat.get("latitude"),
                    "longitude": lonlat.get("longitude"),
                },
                "source": {
                    "id": str(uuid.uuid4()),
                    "name": "4zida.rs",
                    "base_url": "https://www.4zida.rs",
                },
                "seller": {
                    "source_seller_id": jmespath.search("author.id", data),
                    "name": seller_name if seller_name else page["seller"]["name"],
                    "seller_type": "agency" if data.get("advertiserType") else "other",
                    "primary_phone": (
                        phonenumber if phonenumber else page["seller"]["phonenumber"]
                    ),
                    "primary_email": jmespath.search("author.agency.email", data),
                    "website": None,
                },
                "images": images,
            }
        except Exception as e:
            db = next(get_db())
            error_data = Error(
                url=response.url,
                error_type="Spider",
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )
            db.add(error_data)
            db.commit()

    def find_property_data(self, response):
        script = response.css("script:contains('superIndividual')::Text").get()
        try:
            text = re.search(r"self.__next_f.push\(\[(.*?)\]\)", script).group(1)
            text = re.sub(r'\\"', '"', text)
            text = re.sub(r"\\n", "\n", text)
            text = re.sub(r'".*?(\\").*?"', "", text)
            text = re.sub(r"€", " EUR", text)
            text = text.replace("null", "None")
            text = text.replace("false", "False")
            text = text.replace("true", "True")
            text = text[3:-1]
            return eval(text)
        except TypeError:
            return {}
        except Exception as error:
            print(error)
            return {}

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
            return {}

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
