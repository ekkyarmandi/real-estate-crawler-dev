from datetime import datetime
import scrapy
import math
import re
import uuid
import jmespath
import json

from real_estate_scraper.decorators import json_finder


class HaloOglasiNekretnineSpider(scrapy.Spider):
    name = "halooglasi"
    allowed_domains = ["www.halooglasi.com"]
    start_urls = ["https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd"]
    # start_urls = [
    #     "https://www.halooglasi.com/nekretnine/prodaja-stanova/bw-aria---13---beograd-na-vodi/5425644582231?kid=4"
    # ]
    is_paginating = False

    def parse(self, response):
        elements = response.css("div:has(h3.product-title)")
        for el in elements:
            url = el.css("h3.product-title a::attr(href)").get()
            short_description = el.css("p.short-desc::text").get()
            yield response.follow(
                response.urljoin(url),
                callback=self.parse_phonenumber,
                meta=dict(short_description=short_description),
            )
            break

    #     # paginate
    #     total_pages = 0
    #     total_count = 0
    #     if not self.in_pagination:
    #         page_source = (
    #             response.css("script")
    #             .xpath("//*[contains(text(), 'TotalCount')]")
    #             .get()
    #         )
    #         # page_source = response.css('script').xpath("//*[contains(text(), 'TotalCount')]").get()
    #         try:
    #             total_count = re.search(
    #                 r"TotalCount(.*?)(?P<total_count>\d+)", page_source
    #             ).group("total_count")
    #             total_count = int(total_count)
    #             total_pages = math.ceil(total_count / 20)
    #         except Exception as e:
    #             print(e)

    #         # if total_pages:
    #         #     for i in range(2, total_pages + 2):
    #         #         print(response.url + f"?page={i}")

    #     yield dict(
    #         total_pages=total_pages,
    #         total_count=total_count,
    #     )

    def parse_phonenumber(self, response):
        elapsed_time = response.meta.get("download_latency")
        property_data = self.find_property_data(response)
        agency_data = self.find_agency_data(response)

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
                "elapsed_time": elapsed_time,
                "short_description": response.meta.get("short_description"),
                "response_text": response.text,
                "url": response.url,
            },
            body=json.dumps(payload),
            callback=self.parse_detail,
        )

    def parse_detail(self, response):
        elapsed_time = response.meta.get("elapsed_time")
        short_description = response.meta.get("short_description")
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
        image_urls = list(
            map(lambda x: response.urljoin(x), property_data.get("ImageURLs"))
        )

        yield {
            "listing_id": str(uuid.uuid4()),
            "elapsed_time": elapsed_time,
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
            "property": {
                "property_type": jmespath.search(
                    "OtherFields.tip_nekretnine_s", property_data
                ),
                "building_type": jmespath.search(
                    "OtherFields.tip_objekta_s", property_data
                ),
                "size_m2": jmespath.search("OtherFields.kvadratura_d", property_data),
                "floor_number": jmespath.search("OtherFields.sprat_s", property_data),
                # COMMENT: sometime it's not available (sprat_od_s)
                "total_floors": jmespath.search(
                    "OtherFields.sprat_od_s", property_data
                ),
                "rooms": jmespath.search("OtherFields.broj_soba_s", property_data),
                # COMMENT: sometime it's not available (stanje_objekta_s)
                "property_state": jmespath.search(
                    "OtherFields.stanje_objekta_s", property_data
                ),
                # "heating_type": jmespath.search("OtherFields.grejanje_s", property_data),
                # "orientation": None,
                # Note: Skip for the next iterations
                # "has": [
                #     # QUESTIONS: how I can find this data?
                #     # ANSWER: OtherFields.ostalo_ss
                #     {
                #         "id": str(uuid.uuid4()),
                #         # "feature_type": None,
                #         "feature_value": None,
                #         "created_at": now,
                #     }
                # ],
            },
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
            "seller": {
                "source_seller_id": property_data.get("AdvertiserId"),
                "name": jmespath.search("Advertiser.DisplayName", agency_data),
                # COMMENT: if there's number in register put seller type as 'agency'
                "seller_type": (
                    "agency" if agency_data.get("NumberInRegister") else None
                ),
                # "license_id": None,
                # "tax_id": None,
                "primary_phone": phonenumber,
                "primary_email": None,
                "website": agency_data["WebAddress"],
                # "verified": None,
                # "rating": None,
                # "total_listings": None,
                # "active_since": None,
            },
            "images": image_urls,
            # has -> properties table
            # addresses -> addresses table
            # sources -> websites table
            # listed_by -> sellers table
            # contains -> images table
        }

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
