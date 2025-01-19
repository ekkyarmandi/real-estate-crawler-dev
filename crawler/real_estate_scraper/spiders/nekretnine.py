from itemloaders import ItemLoader
import scrapy
from scrapy import Selector
import uuid

from itemloaders.processors import MapCompose
from real_estate_scraper.items import ListingItem, PropertyItem


class NekretnineSpider(scrapy.Spider):
    name = "nekretnine"
    allowed_domains = ["nekretnine.rs"]
    start_urls = [
        "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje-prodaja/prodaja/grad/beograd/lista/po-stranici/10/"
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,  # Add 2 second delay between requests
        "RANDOMIZE_DOWNLOAD_DELAY": True,  # Randomize the delay
        "CONCURRENT_REQUESTS": 1,  # Limit concurrent requests
        "COOKIES_ENABLED": True,  # Enable cookies
        "RETRY_TIMES": 5,  # Reduce retry attempts
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                headers=self.custom_settings["DEFAULT_REQUEST_HEADERS"],
                dont_filter=True,
            )

    def parse(self, response):
        # get all listings
        items = response.css("div.advert-list h2 a::attr(href)").getall()
        for item in items:
            url = response.urljoin(item)
            yield response.follow(url, callback=self.parse_listing)
        # paginations
        max_page = 500
        for i in range(2, max_page + 1):
            next_url = "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje-prodaja/prodaja/grad/beograd/lista/po-stranici/1/stranica/{}/"
            yield response.follow(next_url.format(i), callback=self.parse)

    def parse_listing(self, response):
        response = Selector(response=response)
        # listing loader
        listing_loader = ItemLoader(item=ListingItem(), selector=response)
        listing_loader.add_css("title", "h1::Text")
        listing_loader.add_css(
            "description", "section#opis div.cms-content-inner ::Text"
        )
        listing_loader.add_css("price", "h4[class*=price]::Text")
        listing_loader.add_css(
            "source_id",
            "script:contains(adsKeyword)::Text",
            re=r'id:\s*"([^"]+)"',
        )
        listing = listing_loader.load_item()
        # property loader
        property_loader = ItemLoader(item=PropertyItem(), selector=response)
        property_loader.add_css(
            "size_m2",
            "div.property__main-details ul > li span:contains(Kvadratura)::Text",
        )
        property_loader.add_css(
            "rooms", "div.property__main-details ul > li span:contains(Sobe)::Text"
        )
        property_loader.add_css(
            "property_state", "#detalji ul li:contains(Stanje) strong::Text"
        )
        property_loader.add_css(
            "property_type",
            "script:contains(adsKeyword)::Text",
            re=r'category1:\s*"([^"]+)"',
        )
        floor_number = None
        total_floors = None
        items = response.css(
            "div.property__main-details ul > li span:contains(Sprat)::Text"
        ).getall()
        for item in items:
            if isinstance(item, str) and "/" in item:
                floor_number, total_floors = list(map(str.strip, item.split("/")))
        property_loader.add_value("floor_number", floor_number)
        property_loader.add_value("total_floors", total_floors)
        pitem = property_loader.load_item()
        yield {
            "listing_id": str(uuid.uuid4()),
            "source_id": listing.get("source_id"),
            "title": listing.get("title"),
            "short_description": None,
            "detail_description": listing.get("description"),
            "price": listing.get("price"),
            "price_currency": "EUR",
            "status": "active",
            "valid_from": None,
            "valid_to": None,
            "total_views": 0,
            "url": response.url,
            "raw_data": {
                "html": response.text,
                "data": {},
            },
            ## additional data
            "property": {
                "property_type": pitem.get("property_type"),
                "building_type": None,
                "size_m2": pitem.get("size_m2"),
                "floor_number": pitem.get("floor_number"),
                "total_floors": pitem.get("total_floors"),
                "rooms": pitem.get("rooms"),
                "property_state": pitem.get("property_state"),
            },
            "address": {
                "city": response.css("script:contains(adsKeyword)::Text").re_first(
                    r'location2:\s*"([^"]+)"'
                ),
                "municipality": response.css(
                    "script:contains(adsKeyword)::Text"
                ).re_first(r'location3:\s*"([^"]+)"'),
                "micro_location": response.css(
                    "script:contains(adsKeyword)::Text"
                ).re_first(r'location4:\s*"([^"]+)"'),
                "latitude": response.css("script:contains(ppMap)::Text").re_first(
                    r"ppLat\s*=\s*([-\d.]+)"
                ),
                "longitude": response.css("script:contains(ppMap)::Text").re_first(
                    r"ppLng\s*=\s*([-\d.]+)"
                ),
            },
            "source": {
                "id": str(uuid.uuid4()),
                "name": "Nekretnine.rs",
                "base_url": "https://www.nekretnine.rs",
            },
            "seller": {
                "registry_number": response.css("h4.name + div.label-small").re_first(
                    r"\w+:\s*(\d+)"
                ),
                "source_seller_id": None,
                "name": response.css("h4.name::Text").get(),
                "seller_type": "agency",
                "primary_phone": None,
                "primary_email": None,
                "website": None,
                "active_since": None,
                "tax_id": None,
            },
            "images": [],
        }
