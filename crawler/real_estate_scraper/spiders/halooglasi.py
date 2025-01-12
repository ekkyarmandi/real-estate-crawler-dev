from datetime import datetime
import scrapy
import math
import re
import uuid
import jmespath
import json
import traceback
from decouple import config


from real_estate_scraper.items import PropertyItem
from real_estate_scraper.func import find_agency
from real_estate_scraper.database import get_db
from real_estate_scraper.decorators import json_finder
from real_estate_scraper.spiders.base import BaseSpider
from models.error import Error
from scrapy.selector import Selector
from scrapy.loader import ItemLoader


class HaloOglasiNekretnineSpider(BaseSpider):
    name = "halooglasi"
    allowed_domains = [
        "www.halooglasi.com",
        "scraper-api.smartproxy.com",
    ]
    start_urls = ["https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd"]

    def parse(self, response):
        elements = response.css("div:has(h3.product-title)")
        for el in elements:
            url = el.css("h3.product-title a::attr(href)").get()
            short_description = el.css("p.short-desc::text").get()
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
                    callback=self.parse_phonenumber,
                    errback=self.handle_error,
                    meta={
                        "origin_url": url,
                        "short_description": short_description,
                    },
                )

        # paginate
        total_count = 0
        item_per_page = 20
        if not self.is_paginating:
            page_source = response.css("script:contains(TotalCount)").get()
            try:
                total_count = re.search(
                    r"TotalCount(.*?)(?P<total_count>\d+)", page_source
                ).group("total_count")
                total_count = int(total_count)
                self.total_listings = total_count
                self.total_pages = math.ceil(total_count / item_per_page)
                if self.total_pages:
                    self.is_paginating = True
                    for i in range(2, self.total_pages + 1):
                        next_url = response.url.split("?")[0] + "?page=" + str(i)
                        yield response.follow(next_url, callback=self.parse)
            except Exception as e:
                total_count = 0

    def parse_phonenumber(self, response):
        origin_url = response.meta.get("origin_url")
        short_description = response.meta.get("short_description")
        response_text = jmespath.search("results[0].content", response.json())
        selector = Selector(text=response_text)
        property_data = self.find_property_data(selector)
        agency_data = self.find_agency_data(selector)

        headers = {
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
        }
        payload = {
            "adId": property_data.get("Id"),
            "partyId": property_data.get("AdvertiserId"),
            "adKindId": property_data.get("AdKindId"),
        }

        yield scrapy.Request(
            "https://www.halooglasi.com/AdAdvertiserInfoWidget/AdvertiserPhones",
            method="POST",
            headers=headers,
            meta={
                "property_data": property_data,
                "agency_data": agency_data,
                "elapsed_time": 0,
                "short_description": short_description,
                "response_text": response_text,
                "url": origin_url,
            },
            body=json.dumps(payload),
            callback=self.parse_detail,
            errback=self.handle_error,
        )

    def parse_detail(self, response):
        try:
            short_description = response.meta["short_description"]
            source_url = response.meta.get("url")
            response_text = response.meta.get("response_text")
            it_has_numbers = lambda x: re.search(r"\d{3}", x)

            data = str(response.json())
            phonenumber = re.findall(r">(.*?)<", data)
            phonenumber = list(filter(it_has_numbers, phonenumber))
            phonenumber = ", ".join(phonenumber)

            property_data = response.meta["property_data"]
            agency_data = response.meta["agency_data"]
            geolocation = property_data["GeoLocationRPT"]
            root_url = "https://img.halooglasi.com"
            image_urls = list(
                map(lambda x: root_url + x, property_data.get("ImageURLs"))
            )

            # parse property item
            selector = Selector(text=response_text)
            ploader = ItemLoader(item=PropertyItem(), selector=selector)
            ploader.add_value(
                "property_type",
                jmespath.search("OtherFields.tip_nekretnine_s", property_data),
            )
            ploader.add_value(
                "building_type",
                jmespath.search("OtherFields.tip_objekta_s", property_data),
            )
            ploader.add_value(
                "size_m2",
                jmespath.search("OtherFields.kvadratura_d", property_data),
            )
            ploader.add_value(
                "floor_number",
                jmespath.search("OtherFields.sprat_s", property_data),
            )
            ploader.add_value(
                "total_floors",
                jmespath.search("OtherFields.sprat_od_s", property_data),
            )
            ploader.add_value(
                "rooms",
                jmespath.search("OtherFields.broj_soba_s", property_data),
            )
            ploader.add_value(
                "property_state",
                jmespath.search("OtherFields.stanje_objekta_s", property_data),
            )

            # define seller type
            agency_reg_number = agency_data.get("NumberInRegister")
            seller_type = "agency" if agency_reg_number else None
            if agency_reg_number:
                agency = find_agency(agency_reg_number)
                seller = {
                    "source_seller_id": agency.get("id"),
                    "name": agency.get("name"),
                    "registry_number": agency.get("registryNumber"),
                    "seller_type": seller_type,
                    # "license_id": None,
                    "tax_id": agency.get("taxNumber"),
                    "primary_phone": phonenumber,
                    "primary_email": agency.get("eMail"),
                    "website": agency.get("webPage"),
                    # "verified": None,
                    # "rating": None,
                    # "total_listings": None,
                    "active_since": agency.get("05/02/2021"),
                }
            else:
                seller = {
                    "source_seller_id": property_data.get("AdvertiserId"),
                    "name": jmespath.search("Advertiser.DisplayName", agency_data),
                    # COMMENT: if there's number in register put seller type as 'agency'
                    "seller_type": seller_type,
                    # "license_id": None,
                    "tax_id": None,
                    "primary_phone": phonenumber,
                    "primary_email": None,
                    "website": agency_data["WebAddress"],
                    # "verified": None,
                    # "rating": None,
                    # "total_listings": None, # TODO: calculate total listings
                    "active_since": None,
                }

            yield {
                "listing_id": str(uuid.uuid4()),
                "source_id": property_data.get("Id"),
                "title": property_data.get("Title"),
                # "source_internal_id": None,
                "short_description": short_description,  # get it from property card
                "detail_description": property_data.get("TextHtml"),
                "price": jmespath.search("OtherFields.cena_d", property_data),
                "price_currency": jmespath.search(
                    "OtherFields.cena_d_unit_s", property_data
                ),
                "status": "active",  # if the property is not listed anymore put it as removed
                "valid_from": property_data.get("ValidFrom"),
                "valid_to": property_data.get("ValidTo"),
                "total_views": property_data.get("TotalViews"),
                # "agency_fee": None,
                # "agency_fee_unit": property_data["OtherFields"][
                #     "agencijska_sifra_oglasa_s"
                # ],
                "url": source_url,
                "raw_data": {
                    "html": response_text,
                    "data": {
                        "QuidditaEnvironmyent.CurrentClassified": property_data,
                        "QuidditaEnvironment.CurrentContactData": agency_data,
                    },
                },
                ## additional data
                "property": ploader.load_item(),
                # "property": {
                #     "property_type": jmespath.search(
                #         "OtherFields.tip_nekretnine_s", property_data
                #     ),
                #     "building_type": jmespath.search(
                #         "OtherFields.tip_objekta_s", property_data
                #     ),
                #     "size_m2": jmespath.search(
                #         "OtherFields.kvadratura_d", property_data
                #     ),
                #     "floor_number": jmespath.search(
                #         "OtherFields.sprat_s", property_data
                #     ),
                #     # COMMENT: sometime it's not available (sprat_od_s)
                #     "total_floors": jmespath.search(
                #         "OtherFields.sprat_od_s", property_data
                #     ),
                #     "rooms": jmespath.search("OtherFields.broj_soba_s", property_data),
                #     # COMMENT: sometime it's not available (stanje_objekta_s)
                #     "property_state": jmespath.search(
                #         "OtherFields.stanje_objekta_s", property_data
                #     ),
                #     "heating_type": jmespath.search("OtherFields.grejanje_s", property_data),
                #     "orientation": None,
                #     # Note: Skip for the next iterations
                #     "has": [
                #         # QUESTIONS: how I can find this data?
                #         # ANSWER: OtherFields.ostalo_ss
                #         {
                #             "id": str(uuid.uuid4()),
                #             # "feature_type": None,
                #             "feature_value": None,
                #             "created_at": now,
                #         }
                #     ],
                # },
                "address": {
                    "city": jmespath.search("OtherFields.grad_s", property_data),
                    "municipality": jmespath.search(
                        "OtherFields.lokacija_s", property_data
                    ),
                    "micro_location": jmespath.search(
                        "OtherFields.mikrolokacija_s", property_data
                    ),
                    "latitude": float(geolocation.split(",")[0]),
                    "longitude": float(geolocation.split(",")[1]),
                },
                "source": {
                    "id": str(uuid.uuid4()),
                    "name": "Halo Oglasi Nekretnine",
                    "base_url": "https://www.halooglasi.com",
                },
                "seller": seller,
                "images": image_urls,
                # has -> properties table
                # addresses -> addresses table
                # sources -> websites table
                # listed_by -> sellers table
                # contains -> images table
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

    @json_finder
    def find_property_data(self, response):
        # find QuidditaEnvironment.CurrentClassified using scrapy css selector
        script = response.css(
            "script:contains('QuidditaEnvironment.CurrentClassified')::Text"
        ).get()
        raw_data = re.search(
            r"QuidditaEnvironment.CurrentClassified={(.*?)};", script, re.IGNORECASE
        ).group(1)
        data = "{" + raw_data + "}"
        return data

    @json_finder
    def find_agency_data(self, response):
        # find QuidditaEnvironment.CurrentContactData using scrapy css selector
        script = response.css(
            "script:contains('QuidditaEnvironment.CurrentContactData')::Text"
        ).get()
        raw_data = re.search(
            r"QuidditaEnvironment.CurrentContactData={(.*?)};", script, re.IGNORECASE
        ).group(1)
        data = "{" + raw_data + "}"
        return data
