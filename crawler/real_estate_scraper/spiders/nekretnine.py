from itemloaders import ItemLoader
import scrapy
import uuid
import math

from sqlalchemy import text

from real_estate_scraper.database import get_db
from real_estate_scraper.items import ListingItem, PropertyItem, AddressItem
from real_estate_scraper.spiders.base import BaseSpider


class NekretnineSpider(BaseSpider):
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
        # urls = response.css("div.advert-list h2 a::attr(href)").getall()
        db = next(get_db())
        urls = db.execute(
            text(
                """
                SELECT url
                FROM listings_listing
                WHERE city IS NULL AND url LIKE '%nekretnine%'
                AND status = 'active' LIMIT 1;
                """
            )
        ).fetchall()
        urls = [url[0] for url in urls]
        for url in urls:
            if url not in self.visited_urls:
                url = response.urljoin(url)
                self.visited_urls.append(url)
                yield response.follow(
                    url, callback=self.parse_listing, errback=self.handle_error
                )

        # paginations
        self.total_listings = response.css(
            "h1 + div span:contains(oglasa)::text"
        ).re_first(r"\d+")
        self.total_listings = int(self.total_listings)
        self.total_pages = math.ceil(self.total_listings / 20)
        max_page = 500
        for i in range(2, max_page + 1):
            next_url = "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje-prodaja/prodaja/grad/beograd/lista/po-stranici/1/stranica/{}/"
            # yield response.follow(next_url.format(i), callback=self.parse)

    def parse_listing(self, response):
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
        # address loader
        address_loader = ItemLoader(item=AddressItem(), selector=response)
        address_loader.add_css(
            "city",
            "script:contains(adsKeyword)::Text",
            re=r'"location2":\s*"(.*?)"',
        )
        address_loader.add_css(
            "municipality",
            "script:contains(adsKeyword)::Text",
            re=r'"location3":\s*"(.*?)"',
        )
        address_loader.add_css(
            "micro_location",
            "script:contains(adsKeyword)::Text",
            re=r'"location4":\s*"(.*?)"',
        )
        address_loader.add_css(
            "latitude", "script:contains(ppMap)::Text", re=r"ppLat\s*=\s*([-\d.]+)"
        )
        address_loader.add_css(
            "longitude", "script:contains(ppMap)::Text", re=r"ppLng\s*=\s*([-\d.]+)"
        )
        address_item = address_loader.load_item()
        yield {
            "listing_id": str(uuid.uuid4()),
            "source_id": listing.get("source_id"),
            "title": listing.get("title"),
            "short_description": None,
            "detail_description": listing.get("description"),
            "price": listing.get("price"),
            "price_currency": "EUR",
            "status": "active",
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
                "city": address_item.get("city"),
                "municipality": address_item.get("municipality"),
                "micro_location": address_item.get("micro_location"),
                "latitude": address_item.get("latitude"),
                "longitude": address_item.get("longitude"),
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
            "images": response.css("#top figure img::attr(src)").getall(),
        }
