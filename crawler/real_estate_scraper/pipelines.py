# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from scrapy.exceptions import DropItem
from datetime import datetime as dt
from decouple import config
from real_estate_scraper.database import get_db
from models.error import Report, Error
from models.user import User
from models.queue import Queue
from models.custom_listing import CustomListing
from sqlalchemy import text
import sys
import dj_database_url
import psycopg2
import json
import traceback
import jmespath

from real_estate_scraper.templates.sql.listing import listing_insert_query
from real_estate_scraper.templates.sql.error import error_insert_query


def keep_url_only(item):
    return dict(url=item.get("url", "URL not exists"))


class PostgreSQLConnection:
    conn = None
    cursor = None

    def __init__(self):
        try:
            if not self.conn:
                db_config = dj_database_url.parse(config("DB_URL"))
                self.conn = psycopg2.connect(
                    database=db_config["NAME"],
                    user=db_config["USER"],
                    password=db_config["PASSWORD"],
                    host=db_config["HOST"],
                    port=db_config["PORT"],
                )
                self.cursor = self.conn.cursor()
        except Exception as err:
            raise ConnectionError(
                "Could not establish connection with PostgreSQL database: {0}".format(
                    err
                )
            )


class SourcesPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # query existing source
        q = "SELECT id,base_url FROM listings_source WHERE base_url='{}';".format(
            item["source"]["base_url"]
        )
        self.db.cursor.execute(q)
        existing_source = self.db.cursor.fetchone()
        if existing_source:
            item["source"]["id"] = str(existing_source[0])
            return item
        # construct source item
        source_item = dict(
            id=item["source"]["id"],
            name=item["source"]["name"],
            base_url=item["source"]["base_url"],
            scraper_config=json.dumps({}),
        )
        # write the insertion query
        q = """
        INSERT INTO listings_source (
            id, created_at, updated_at,
            name,
            base_url,
            scraper_config
        ) VALUES (
            %(id)s, now(), now(),
            %(name)s,
            %(base_url)s,
            %(scraper_config)s
        ) ON CONFLICT DO NOTHING;
        """
        # execute query
        try:
            self.db.cursor.execute(q, source_item)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            raise ValueError("Source insertion failed: {0}".format(err))
        return item


class ListingPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def __queue_new_listings(self, spider):
        db = next(get_db())
        today = dt.now().strftime(r"%Y-%m-%d")
        users = db.query(User).all()
        # query new listings
        cols = [
            "id",
            "url",
            "city",
            "price",
            "municipality",
            "micro_location",
            "size_m2",
            "rooms",
        ]
        q = text(
            f"""
            SELECT
                listings.id,
                listings.url,
                listings.city,
                listings.price,
                listings.municipality,
                listings.micro_location,
                COALESCE(MAX(properties.size_m2), 0) AS size_m2,
                COALESCE(MAX(properties.rooms), 0) AS rooms
            FROM listings_listing as listings
            JOIN listings_property as properties ON listings.id = properties.listing_id
            WHERE listings.created_at >= '{today}'
            AND listings.url LIKE '%{spider.name}%'
            GROUP BY listings.id;
            """
        )
        result = db.execute(q)
        listings = result.fetchall()
        # convert raw data into custom listings
        listings = [dict(zip(cols, listing)) for listing in listings]
        listings = [CustomListing(**item) for item in listings]
        # send all the listings via telegram bot as notifications
        for user in users:
            for listing in listings:
                if listing.validate_settings(user.settings):
                    # create queue
                    queue = Queue(listing_id=listing.id, user_id=user.id)
                    try:
                        db.add(queue)
                        db.commit()
                    except Exception as err:
                        db.rollback()

    def process_item(self, item, spider):
        # query the existing listing by url
        q = "SELECT * FROM listings_listing WHERE url='{}';".format(item["url"])
        self.db.cursor.execute(q)
        existing_listing = self.db.cursor.fetchone()
        if existing_listing:
            item["listing_id"] = existing_listing[2]
        # construct listing data
        listing_item = dict(
            listing_id=item["listing_id"],
            source_id=item["source"]["id"],
            url=item["url"],
            title=item["title"],
            short_description=item["short_description"],
            detail_description=item["detail_description"],
            price=item["price"],
            price_currency=item["price_currency"],
            status=item["status"],
            valid_from=item["valid_from"],
            valid_to=item["valid_to"],
            total_views=item["total_views"],
            city=item["address"]["city"],
            municipality=item["address"]["municipality"],
            micro_location=item["address"]["micro_location"],
            latitude=item["address"]["latitude"],
            longitude=item["address"]["longitude"],
        )
        if not listing_item["price"]:
            listing_item["price"] = -1
        # insert value
        try:
            self.db.cursor.execute(listing_insert_query, listing_item)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            # Insert error to db
            error_item = dict(
                url=item["url"],
                error_type="Listing insertion",
                error_message=str(err),
                error_traceback=traceback.format_exc(),
            )
            self.db.cursor.execute(error_insert_query, error_item)
            self.db.conn.commit()
            raise DropItem("Listing insertion failed: {0}".format(err))

        # remove listing url from error if it exists
        db = next(get_db())
        db.query(Error).filter(Error.url == item["url"]).delete()
        db.commit()
        return item

    def open_spider(self, spider):
        db = next(get_db())
        # Load exisiting urls
        if spider.settings.get("LOAD_EXISTING_URLS"):
            q = text(
                f"SELECT url FROM listings_listing WHERE url LIKE '%{spider.name}%';"
            )
            result = db.execute(q)
            visited_urls = result.fetchall()
            spider.visited_urls = [url[0] for url in visited_urls]
        try:
            # Create new report
            report = Report(source_name=spider.name)
            db.add(report)
            db.commit()
            db.refresh(report)
            spider.report_id = report.id
        except Exception as err:
            db.rollback()
            raise ValueError("Error on spider close: {0}".format(err))

    def close_spider(self, spider):
        # Access total_pages and total_listings from the spider
        total_pages = getattr(spider, "total_pages", 0)
        total_listings = getattr(spider, "total_listings", 0)
        visited_urls = getattr(spider, "visited_urls", [])
        total_actual_listings = len(visited_urls)
        # Get spider stats
        stats = spider.crawler.stats.get_stats()
        # Calculate elapsed time
        start_time = stats.get("start_time", 0)
        elapsed_time = dt.now(start_time.tzinfo) - start_time
        # Update the existing report using spider.report_id
        db = next(get_db())
        try:
            report = db.query(Report).filter(Report.id == spider.report_id).one()
            report.total_pages = total_pages
            report.total_listings = total_listings
            report.total_actual_listings = total_actual_listings
            report.item_scraped_count = stats.get("item_scraped_count", 0)
            report.item_dropped_count = stats.get("item_dropped_count", 0)
            report.total_new_listings = spider.total_new_listings
            report.total_changed_listings = spider.total_changed_listings
            report.response_error_count = stats.get("log_count/ERROR", 0)
            report.elapsed_time_seconds = elapsed_time.total_seconds()
            db.commit()
        except Exception as err:
            db.rollback()
            raise ValueError("Error on spider close: {0}".format(err))

        # queue new listings
        self.__queue_new_listings(spider)


class RawDataPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # construct raw data item
        raw_data_item = dict(
            listing_id=item["listing_id"],
            html=item["raw_data"]["html"],
            data=json.dumps(item["raw_data"]["data"]),
        )
        # write the insert query
        q = """
        INSERT INTO listings_rawdata (id, created_at, updated_at, listing_id, html, data)
        VALUES (uuid_generate_v4(), now(), now(), %(listing_id)s, %(html)s, %(data)s);
        """
        # execute the query
        try:
            self.db.cursor.execute(q, raw_data_item)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            raise ValueError("Raw data insertion failed: {0}".format(err))
        return item


class PropertyPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # construct property item
        property_item = dict(
            listing_id=item["listing_id"],
            property_type=item["property"]["property_type"],
            building_type=item["property"]["building_type"],
            size_m2=item["property"]["size_m2"],
            floor_number=item["property"]["floor_number"],
            total_floors=item["property"]["total_floors"],
            rooms=item["property"]["rooms"],
            property_state=item["property"]["property_state"],
        )
        columns = [
            "size_m2",
            "floor_number",
            "total_floors",
            "rooms",
        ]
        for col in columns:
            value = property_item[col]
            if isinstance(value, str) and "+" in value:
                property_item[col] = value.replace("+", "")
        # write the insert query
        q = """
        INSERT INTO listings_property (
            id, created_at, updated_at,
            listing_id,
            property_type,
            building_type,
            size_m2,
            floor_number,
            total_floors,
            rooms,
            property_state
        ) VALUES (
            uuid_generate_v4(), now(), now(),
            %(listing_id)s,
            %(property_type)s,
            %(building_type)s,
            %(size_m2)s,
            %(floor_number)s,
            %(total_floors)s,
            %(rooms)s,
            %(property_state)s
        ) ON CONFLICT DO NOTHING;
        """
        # execute query
        try:
            self.db.cursor.execute(q, property_item)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            # Insert error to db
            error_item = dict(
                url=item["url"],
                error_type="Property insertion",
                error_message=str(err),
                error_traceback=traceback.format_exc(),
            )
            self.db.cursor.execute(error_insert_query, error_item)
            self.db.conn.commit()
            raise DropItem("Error on property insertion: {0}".format(err))
        return item


class ImagesPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # construct image items
        image_items = []
        images = item["images"]
        for i, image_url in enumerate(images):
            image_id = f"{item['listing_id']}_{i}"
            # source_url = supabase_uploader(image_url, image_id)
            image_items.append(
                (
                    item["listing_id"],
                    image_url,
                    image_url,
                    i + 1,
                )
            )
        # write the insert query
        q = """
        INSERT INTO listings_image (
            id, created_at, updated_at,
            listing_id,
            source_url,
            url,
            sequence_number
        ) VALUES (
            uuid_generate_v4(), now(), now(),
            %s,
            %s,
            %s,
            %s
        ) ON CONFLICT DO NOTHING;
        """
        # execute query
        try:
            self.db.cursor.executemany(q, image_items)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            raise ValueError("Image insertion failed: {0}".format(err))
        return item


class SellersPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # construct seller item
        seller_type = item["seller"]["seller_type"]
        if not seller_type:
            seller_type = "person"
        seller_name = jmespath.search("seller.name", item) or "Unknown Seller"
        seller_item = dict(
            source_id=item["source"]["id"],
            source_seller_id=item["seller"]["source_seller_id"],
            name=seller_name,
            seller_type=seller_type,
            primary_phone=item["seller"]["primary_phone"],
            primary_email=item["seller"]["primary_email"],
            website=item["seller"]["website"],
        )
        # write the insertion query
        q = """
        INSERT INTO listings_seller (
            id, created_at, updated_at,
            source_id,
            source_seller_id,
            name,
            seller_type,
            primary_phone,
            primary_email,
            website
        ) VALUES (
            uuid_generate_v4(), now(), now(),
            %(source_id)s,
            %(source_seller_id)s,
            %(name)s,
            %(seller_type)s,
            %(primary_phone)s,
            %(primary_email)s,
            %(website)s
        ) ON CONFLICT DO NOTHING;
        """
        # execute query
        try:
            self.db.cursor.execute(q, seller_item)
            self.db.conn.commit()
        except Exception as err:
            self.db.conn.rollback()
            raise ValueError("Seller insertion failed: {0}".format(err))
        item.pop("raw_data")
        return item


class ListingChangePipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # query existing listing
        q = f"""
        SELECT
            ll.price,
            ll.status,
            ll.valid_from,
            ll.valid_to,
            ll.detail_description,
            ll.short_description,
            rd.id AS raw_data_id
        FROM listings_listing ll
        JOIN listings_property lp ON lp.listing_id = ll.id
        JOIN listings_rawdata rd ON rd.listing_id = ll.id
        WHERE ll.id = '{item["listing_id"]}';
        """
        self.db.cursor.execute(q)
        columns = [
            "price",
            "status",
            "valid_from",
            "valid_to",
            "detail_description",
            "short_description",
        ]
        listing = self.db.cursor.fetchone()
        if not listing:
            spider.total_new_listings += 1
        elif listing:
            raw_data_id = listing[-1]
            listing = dict(zip(columns, listing))
            # validate the price
            price = listing["price"]
            if not price:
                listing["price"] = -1
            else:
                listing["price"] = round(float(listing["price"]), 2)
            # validate valid_from and valid_to
            if listing["valid_from"]:
                listing["valid_from"] = listing["valid_from"].strftime(
                    r"%Y-%m-%dT%H:%M:%S"
                )
            else:
                listing["valid_from"] = None
            if listing["valid_to"]:
                listing["valid_to"] = listing["valid_to"].strftime(r"%Y-%m-%dT%H:%M:%S")
            else:
                listing["valid_to"] = None
            try:
                valid_from = dt.strptime(item["valid_from"], r"%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                valid_from = dt.strptime(item["valid_from"], r"%Y-%m-%dT%H:%M:%SZ")
            except TypeError:
                valid_from = None
            try:
                valid_to = dt.strptime(item["valid_to"], r"%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                valid_to = dt.strptime(item["valid_to"], r"%Y-%m-%dT%H:%M:%SZ")
            except TypeError:
                valid_to = None
            # construct listing change item by combining ListingItem with ListingChangeItem
            new_listing = dict(
                price=item["price"],
                status=item["status"],
                valid_from=(
                    valid_from.strftime(r"%Y-%m-%dT%H:%M:%S") if valid_from else None
                ),
                valid_to=(
                    valid_to.strftime(r"%Y-%m-%dT%H:%M:%S") if valid_to else None
                ),
                detail_description=item["detail_description"],
                short_description=item["short_description"],
            )
            # validate new listing values
            try:
                new_listing["price"] = round(float(new_listing["price"]), 2)
            except (ValueError, TypeError):
                new_listing["price"] = -1
            # check the changes
            change_items = []
            for col in ["price", "short_description", "detail_description"]:
                old_value = listing[col]
                new_value = new_listing[col]
                if old_value != new_value:
                    change = dict(
                        listing_id=item["listing_id"],
                        raw_data_id=raw_data_id,
                        change_type=f"{col}_change",
                        field=col,
                        old_value=old_value,
                        new_value=new_value,
                    )
                    change_items.append(list(change.values()))
            if len(change_items) > 0:
                spider.total_changed_listings += 1
                # execute query
                q = """
                INSERT INTO listings_listingchange (
                    id, created_at, updated_at,
                    listing_id,
                    raw_data_id,
                    change_type,
                    field,
                    old_value,
                    new_value,
                    changed_at
                ) VALUES (
                    uuid_generate_v4(), now(), now(),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    now()
                ) ON CONFLICT DO NOTHING;
                """
                # execute query
                try:
                    self.db.cursor.executemany(q, change_items)
                    self.db.conn.commit()
                except Exception as err:
                    self.db.conn.rollback()
                    # Insert error to db
                    error_item = dict(
                        url=item["url"],
                        error_type="Listing changes insertion",
                        error_message=str(err),
                        error_traceback=traceback.format_exc(),
                    )
                    self.db.cursor.execute(error_insert_query, error_item)
                    self.db.conn.commit()
                    raise ValueError(
                        "Error on listing changes insertion: {0}".format(err)
                    )
