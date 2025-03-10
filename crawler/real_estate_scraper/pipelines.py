# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from scrapy.exceptions import DropItem
from datetime import datetime as dt
from decouple import config
from models.listing_change import PreviousListing
from real_estate_scraper.database import get_db
from models.error import Report, Error
from models.user import User
from models.queue import Queue
from models.custom_listing import CustomListing
from models import Agent, Seller
from sqlalchemy import text
import dj_database_url
import psycopg2
import json
import traceback
import jmespath
import uuid
import re
from real_estate_scraper.templates.sql.listing import listing_insert_query
from real_estate_scraper.templates.sql.error import error_insert_query
from models.property import Property


def keep_url_only(item):
    return dict(url=item.get("url", "URL not exists"))


class PostgreSQLConnection:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            if not self.conn or self.conn.closed:
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

    def ensure_connection(self):
        try:
            # Test if connection is alive
            self.cursor.execute("SELECT 1")
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            # Reconnect if connection is closed
            self.connect()

    def execute(self, query, params=None):
        try:
            self.ensure_connection()
            self.cursor.execute(query, params)
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            # Try one more time
            self.connect()
            self.cursor.execute(query, params)

    def commit(self):
        self.ensure_connection()
        self.conn.commit()

    def rollback(self):
        self.ensure_connection()
        self.conn.rollback()


class DatabaseConnection:
    _instance = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._psql = PostgreSQLConnection()
            cls._instance._db = next(get_db())
        return cls._instance

    @property
    def psql(self):
        return self._psql

    @property
    def db(self):
        return self._db


class BasePipeline:
    def __init__(self):
        self.conn = DatabaseConnection()
        self.db = self.conn.db  # SQLAlchemy session
        self.psql = self.conn.psql  # PostgreSQL connection


class SourcesPipeline(BasePipeline):
    def process_item(self, item, spider):
        # query existing source
        q = "SELECT id,base_url FROM listings_source WHERE base_url='{}';".format(
            item["source"]["base_url"]
        )
        self.psql.cursor.execute(q)
        existing_source = self.psql.cursor.fetchone()
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
            self.psql.cursor.execute(q, source_item)
            self.psql.conn.commit()
        except Exception as err:
            self.psql.conn.rollback()
            raise ValueError("Source insertion failed: {0}".format(err))
        return item


class SellersPipeline(BasePipeline):
    def __init__(self):
        super().__init__()
        self.sellers = (
            {}
        )  # COMMENTS: sellers would consist of seller_id and registry_number

    def process_item(self, item, spider):
        registry_number = jmespath.search("seller.registry_number", item)
        # Query the existing seller
        seller_type = jmespath.search("seller.seller_type", item)
        if not seller_type:
            seller_type = "person"
        seller_name = jmespath.search("seller.name", item) or "Unknown Seller"
        source_seller_id = jmespath.search("seller.source_seller_id", item)
        seller = (
            self.db.query(Seller)
            .filter(
                Seller.source_seller_id == str(source_seller_id),
                Seller.name == seller_name,
                Seller.seller_type == seller_type,
            )
            .first()
        )
        # if seller exists, grab the seller id
        if seller:
            item["seller"]["id"] = str(seller.id)
        # if not, insert new seller
        else:
            seller_item = Seller(
                source_seller_id=source_seller_id,
                name=seller_name,
                seller_type=seller_type,
                primary_phone=jmespath.search("seller.primary_phone", item),
                primary_email=jmespath.search("seller.primary_email", item),
                website=jmespath.search("seller.website", item),
            )
            self.db.add(seller_item)
            self.db.commit()
            self.db.refresh(seller_item)
            item["seller"]["id"] = str(seller_item.id)
        # collect the seller id and registry number
        if registry_number:
            seller_id = jmespath.search("seller.id", item)
            self.sellers[seller_id] = registry_number
        return item

    def close_spider(self, spider):
        for seller_id, registry_number in self.sellers.items():
            seller = self.db.query(Seller).filter(Seller.id == seller_id).first()
            if seller and seller.seller_type == "agency" and not seller.agent_id:
                agent = (
                    self.db.query(Agent)
                    .filter(Agent.registry_number == str(registry_number))
                    .first()
                )
                if agent:
                    seller.agent_id = agent.id
                    self.db.commit()
                    self.db.refresh(seller)


class ListingPipeline(BasePipeline):
    def __init__(self):
        super().__init__()

    def __queue_new_listings(self, spider):
        today = dt.now().strftime(r"%Y-%m-%d")
        users = self.db.query(User).all()
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
                ll.id,
                ll.url,
                ll.city,
                ll.price,
                ll.municipality,
                ll.micro_location,
                lp.size_m2,
                lp.rooms
            FROM listings_listing as ll
            JOIN listings_property as lp ON lp.listing_id = ll.id
            WHERE ll.price > 0 AND lp.size_m2 > 0 AND ll.created_at >= '{today}'
            AND ll.status = 'active' AND ll.url LIKE '%{spider.name}%'
            ORDER BY ll.created_at DESC;
            """
        )
        result = self.db.execute(q)
        listings = result.fetchall()
        # convert raw data into custom listings
        listings = [dict(zip(cols, listing)) for listing in listings]
        listings = [CustomListing(**item) for item in listings]
        # send all the listings via telegram bot as notifications
        for user in users:
            user_queues = (
                self.db.query(Queue.listing_id).filter(Queue.user_id == user.id).all()
            )
            user_queues = [u[0] for u in user_queues]
            for l in listings:
                if l.id not in user_queues and l.validate_settings(user.settings):
                    # create queue
                    queue = Queue(listing_id=l.id, user_id=user.id)
                    try:
                        self.db.add(queue)
                        self.db.commit()
                    except Exception:
                        self.db.rollback()

        # for listing in listings:
        #     # Query all users who already have this listing in their queue
        #     excluded_users = (
        #         self.db.query(Queue.user_id)
        #         .filter(Queue.listing_id == listing.id)
        #         .all()
        #     )
        #     excluded_user_ids = [user_id[0] for user_id in excluded_users]
        #     for user in users:
        #         # Skip users who already have this listing in their queue
        #         if user.id in excluded_user_ids:
        #             continue
        #         # Only validate settings for users not in the exclusion list
        #         if listing.validate_settings(user.settings):
        #             queue = Queue(listing_id=listing.id, user_id=user.id)
        #             try:
        #                 self.db.add(queue)
        #                 self.db.commit()
        #             except Exception as err:
        #                 self.db.rollback()

    def process_item(self, item, spider):
        # query the existing listing by url
        q = text(f"SELECT * FROM listings_listing WHERE url='{item['url']}';")
        existing_listing = self.db.execute(q).fetchone()
        if not existing_listing:
            spider.total_new_listings += 1
        else:
            item["listing_id"] = existing_listing[2]

        # construct listing data
        listing_item = dict(
            listing_id=item["listing_id"],
            source_id=item["source"]["id"],
            seller_id=item["seller"]["id"],
            url=item["url"],
            title=item["title"],
            short_description=item["short_description"],
            detail_description=item["detail_description"],
            price=item["price"],
            price_currency=item["price_currency"],
            status=item["status"],
            city=item["address"]["city"],
            municipality=item["address"]["municipality"],
            micro_location=item["address"]["micro_location"],
            latitude=item["address"]["latitude"],
            longitude=item["address"]["longitude"],
        )
        listing_price = item["price"]
        if not listing_price:
            listing_item["price"] = -1
        elif isinstance(listing_price, str) and not re.search(r"\d+", listing_price):
            listing_item["price"] = -1
        # insert value
        try:
            self.db.execute(text(listing_insert_query), listing_item)
            self.db.commit()
        except Exception as err:
            self.db.rollback()
            spider.total_new_listings -= 1
            if not listing_item.get("title"):
                q = text(
                    f"""
                    UPDATE listings_listing SET status='removed', updated_at=now()
                    WHERE url='{item["url"]}';
                    """
                )
                self.db.execute(q)
                self.db.commit()
                raise DropItem("Listing insertion failed: {0}".format(err))
            # Insert error to db
            db = next(get_db())
            error = Error(
                url=item["url"],
                error_type="Listing insertion",
                error_message=str(err),
                error_traceback=traceback.format_exc(),
            )
            db.add(error)
            db.commit()
            db.close()
            raise DropItem("Listing insertion failed: {0}".format(err))

        # remove listing url from error if it exists
        self.db.query(Error).filter(Error.url == item["url"]).delete()
        self.db.commit()
        return item

    def open_spider(self, spider):
        # Load exisiting urls
        load_existings = spider.settings.get("LOAD_EXISTING_URLS")
        if load_existings and eval(load_existings):
            q = text(
                f"SELECT url FROM listings_listing WHERE url LIKE '%{spider.name}%';"
            )
            result = self.db.execute(q)
            visited_urls = result.fetchall()
            spider.visited_urls = [url[0] for url in visited_urls]
        try:
            # Create new report
            report = Report(source_name=spider.name)
            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)
            spider.report_id = report.id
        except Exception as err:
            self.db.rollback()
            raise ValueError("Error on spider close: {0}".format(err))

    def close_spider(self, spider):
        # Access total_pages and total_listings from the spider
        total_pages = getattr(spider, "total_pages", 0)
        total_listings = getattr(spider, "total_listings", 0)
        visited_urls = getattr(spider, "visited_urls", [])
        total_actual_listings = len(list(set(visited_urls)))
        # Get spider stats
        stats = spider.crawler.stats.get_stats()
        # Calculate elapsed time
        start_time = stats.get("start_time", 0)
        elapsed_time = dt.now(start_time.tzinfo) - start_time
        # Update the existing report using spider.report_id
        try:
            report = self.db.query(Report).filter(Report.id == spider.report_id).one()
            report.total_pages = total_pages
            report.total_listings = total_listings
            report.total_actual_listings = total_actual_listings
            report.item_scraped_count = stats.get("item_scraped_count", 0)
            report.item_dropped_count = stats.get("item_dropped_count", 0)
            report.total_new_listings = spider.total_new_listings
            report.total_changed_listings = spider.total_changed_listings
            report.response_error_count = stats.get("log_count/ERROR", 0)
            report.elapsed_time_seconds = elapsed_time.total_seconds()
            self.db.commit()
        except Exception as err:
            self.db.rollback()
            raise ValueError("Error on spider close: {0}".format(err))

        # queue new listings
        self.__queue_new_listings(spider)


class RawDataPipeline(BasePipeline):
    def process_item(self, item, spider):
        # clean up HTML data related to halooglasi
        if "halooglasi" in item["url"]:
            item["raw_data"]["html"] = ""
        # COMMENT: figure out what 4zida criteria that would be allowed for raw data
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
            self.psql.cursor.execute(q, raw_data_item)
            self.psql.conn.commit()
        except Exception as err:
            self.psql.conn.rollback()
            raise ValueError("Raw data insertion failed: {0}".format(err))
        return item


class PropertyPipeline(BasePipeline):
    def process_item(self, item, spider):
        # Query existing property
        existing_property = (
            self.db.query(Property)
            .filter(Property.listing_id == item["listing_id"])
            .first()
        )

        if existing_property:
            item["property"]["id"] = str(existing_property.id)
            return item

        # construct property item
        property_item = dict(
            id=uuid.uuid4(),
            listing_id=item["listing_id"],
            property_type=item["property"]["property_type"],
            building_type=item["property"]["building_type"],
            size_m2=item["property"]["size_m2"],
            floor_number=item["property"]["floor_number"],
            total_floors=item["property"]["total_floors"],
            rooms=item["property"]["rooms"],
            property_state=item["property"]["property_state"],
        )

        # Clean up values containing "+"
        columns = ["size_m2", "floor_number", "total_floors", "rooms"]
        for col in columns:
            value = property_item[col]
            if isinstance(value, str) and "+" in value:
                property_item[col] = value.replace("+", "")

        # write the insert query
        q = """
        INSERT INTO listings_property (
            id, created_at, updated_at,
            listing_id, property_type, building_type,
            size_m2, floor_number, total_floors,
            rooms, property_state
        ) VALUES (
            %(id)s, now(), now(),
            %(listing_id)s, %(property_type)s, %(building_type)s,
            %(size_m2)s, %(floor_number)s, %(total_floors)s,
            %(rooms)s, %(property_state)s
        ) ON CONFLICT DO NOTHING;
        """
        # execute the query
        try:
            self.psql.cursor.execute(q, property_item)
            self.psql.conn.commit()
            item["property"]["id"] = str(property_item["id"])
        except Exception as err:
            self.psql.rollback()
            # Insert error to db
            error = Error(
                url=item["url"],
                error_type="Property insertion",
                error_message=str(err),
                error_traceback=traceback.format_exc(),
            )
            self.db.add(error)
            self.db.commit()
            raise DropItem("Error on property insertion: {0}".format(err))
        return item


class ImagesPipeline(BasePipeline):
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
            uuid_generate_v4(), now(), now(), %s, %s, %s, %s
        ) ON CONFLICT DO NOTHING;
        """
        # execute query
        for image in image_items:
            try:
                self.psql.execute(q, image)
                self.psql.commit()
            except Exception as err:
                self.psql.rollback()
                raise ValueError("Image insertion failed: {0}".format(err))
        return item


class ListingChangePipeline(BasePipeline):
    def process_item(self, item, spider):
        # query existing listing
        q = f"""
        SELECT
            ll.url,
            ll.price,
            ll.status,
            ll.city,
            ll.municipality,
            ll.micro_location,
            ll.detail_description,
            ll.short_description,
            lp.size_m2,
            lp.rooms,
            rd.id AS raw_data_id
        FROM listings_listing ll
        JOIN listings_property lp ON lp.listing_id = ll.id
        JOIN listings_rawdata rd ON rd.listing_id = ll.id
        WHERE ll.id = '{item["listing_id"]}';
        """
        self.psql.cursor.execute(q)
        columns = [
            "url",
            "price",
            "status",
            "city",
            "municipality",
            "micro_location",
            "detail_description",
            "short_description",
            "size_m2",
            "rooms",
            "raw_data_id",
        ]
        listing = self.psql.cursor.fetchone()  # existing listing
        if not listing:
            spider.total_new_listings += 1
        elif listing:
            listing = dict(zip(columns, listing))
            previous_listing = PreviousListing(**listing)
            new_listing = PreviousListing(
                price=item["price"],
                status=item["status"],
                city=item["address"]["city"],
                municipality=item["address"]["municipality"],
                micro_location=item["address"]["micro_location"],
                short_description=item["short_description"],
                detail_description=item["detail_description"],
                size_m2=item["property"]["size_m2"],
                rooms=item["property"]["rooms"],
            )
            # check the changes
            columns_to_check = [
                "price",
                "city",
                "municipality",
                "micro_location",
                "short_description",
                "detail_description",
                "size_m2",
                "rooms",
            ]
            change_items = []
            for col in columns_to_check:
                old_value = getattr(previous_listing, col)
                new_value = getattr(new_listing, col)
                if old_value != new_value:
                    change = dict(
                        listing_id=item["listing_id"],
                        raw_data_id=previous_listing.raw_data_id,
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
                    uuid_generate_v4(), now(), now(), %s, %s, %s, %s, %s, %s, now()
                ) ON CONFLICT DO NOTHING;
                """
                # execute query
                try:
                    self.psql.cursor.executemany(q, change_items)
                    self.psql.conn.commit()

                    ## UPDATE LISTINGS
                    # convert the new_value to SET clause
                    new_values = {}
                    for change in change_items:
                        field = change[3]
                        if field in [
                            "price",
                            "city",
                            "municipality",
                            "micro_location",
                            "short_description",
                            "detail_description",
                        ]:
                            new_values.update({field: change[5]})
                    if "price" in new_values and not new_values["price"]:
                        new_values["price"] = -1
                    set_clause = ", ".join([f"{k} = %s" for k in new_values.keys()])
                    # update the updated_at field on the listings table
                    listing_id = item["listing_id"]
                    q = f"""
                    UPDATE listings_listing SET updated_at=now(), {set_clause}
                    WHERE id='{listing_id}';
                    """
                    if set_clause != "":
                        self.psql.cursor.execute(q, list(new_values.values()))
                        self.psql.conn.commit()

                    ## UPDATE PROPERTY
                    new_values = {}
                    for change in change_items:
                        field = change[3]
                        if field in ["size_m2", "rooms"]:
                            new_values.update({field: change[5]})
                    set_clause = ", ".join([f"{k} = %s" for k in new_values.keys()])
                    # update the updated_at field on the listings table
                    listing_id = item["listing_id"]
                    q = f"""
                    UPDATE listings_property SET updated_at=now(), {set_clause}
                    WHERE listing_id='{listing_id}';
                    """
                    if set_clause != "":
                        self.psql.cursor.execute(q, list(new_values.values()))
                        self.psql.conn.commit()
                except Exception as err:
                    self.psql.conn.rollback()
                    # Insert error to db
                    db = next(get_db())
                    error = Error(
                        url=item["url"],
                        error_type="Listing changes insertion",
                        error_message=str(err),
                        error_traceback=traceback.format_exc(),
                    )
                    db.add(error)
                    db.commit()
                    db.close()
                    raise ValueError(
                        "Error on listing changes insertion: {0}".format(err)
                    )
