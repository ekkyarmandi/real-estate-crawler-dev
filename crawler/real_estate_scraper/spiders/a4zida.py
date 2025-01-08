import json
import math
import re
import uuid
import scrapy
import jmespath
import traceback
from decouple import config

from real_estate_scraper.func import clean_double_quotes
from real_estate_scraper.database import get_db
from real_estate_scraper.spiders.base import BaseSpider
from models.error import Error

from scrapy.selector import Selector


class A4zidaSpider(BaseSpider):
    name = "4zida"
    allowed_domains = ["www.4zida.rs", "scraper-api.smartproxy.com"]
    start_urls = ["https://www.4zida.rs/prodaja-stanova/beograd"]

    def parse(self, response):
        # find property urls
        urls = response.css("div:has(button):has(a) > a:has(p)::attr(href)").getall()
        urls = list(dict.fromkeys((urls)))
        for url in urls:
            if url not in self.visited_urls:
                url = response.urljoin(url)
                self.visited_urls.append(url)
                endpoint = "https://scraper-api.smartproxy.com/v2/scrape"
                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "authorization": "Basic " + config("SMARTPROXY_API_KEY"),
                }
                yield scrapy.Request(
                    url=endpoint,
                    method="POST",
                    headers=headers,
                    body=json.dumps({"url": url}),
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta={"origin_url": url},
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
            self.total_pages = total_pages
            for i in range(2, 101):
                next_url = response.url.split("?")[0] + "?strana=" + str(i)
                yield response.follow(next_url)

    def parse_detail(self, response):
        try:
            html = jmespath.search("results[0].content", response.json())
            origin_url = response.meta["origin_url"]
            response = Selector(text=html)
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

            # refine the page data
            price = data.get("price")
            if price:
                if isinstance(price, str):
                    price = price.replace(".", "")
                    price = price.replace(",", ".")
                    price = float(price)
                data["price"] = price

            yield {
                "listing_id": str(uuid.uuid4()),
                "source_id": data.get("id"),
                "title": data.get("title", page["title"]),
                "short_description": data.get("humanReadableDescription"),
                "detail_description": data.get("desc", page["descriptions"]),
                "price": data.get("price", page["price"]),
                "price_currency": "EUR",
                "status": "active",
                "valid_from": None,  # COMMENT: not sure which data point to look
                "valid_to": None,  # COMMENT: not sure which data point to look
                "total_views": 0,
                "url": origin_url,
                "raw_data": {
                    "html": html,
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
                    "rooms": page["property"]["rooms"],
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
                url=origin_url,
                error_type="Spider",
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )
            db.add(error_data)
            db.commit()

    def find_property_data(self, response):
        script = response.css("script:contains('superIndividual')::Text").get()
        output = {}
        if script:
            try:
                text = re.search(r"self.__next_f.push\(\[(.*?)\]\)", script).group(1)
                text = re.sub(r'\\{2,}"', '\\"', text)
                text = re.sub(r'//{2,}"', "//", text)
                text = re.sub(r'\\"', '"', text)
                # text = re.sub(r"\\n", "\n", text)
                text = re.sub(r'".*?(\\").*?"', "", text)
                text = re.sub(r"€", " EUR", text)
                new_text = text[3:-1]
                new_text = clean_double_quotes(new_text)
                output = json.loads(new_text)
            except Exception as err:
                output = {}
        return output

    def find_longitude_latitude(self, response):
        script = response.css("script:contains('longitude')::Text").get()
        output = {}
        if script:
            try:
                text = re.search(r"self.__next_f.push\(\[(.*?)\]\)", script).group(1)
                text = re.sub(r'\\{2,}"', '\\"', text)
                text = re.sub(r'\\"', '"', text)
                text = re.search(
                    r'"latitude":[0-9.]+\s*,\s*"longitude":[0-9.]+', text
                ).group()
                output = json.loads("{" + text + "}")
            except:
                output = {}
        return output

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
