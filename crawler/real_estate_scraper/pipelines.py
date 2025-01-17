# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from scrapy.exceptions import DropItem
from datetime import datetime as dt
from decouple import config
from real_estate_scraper.func import change_value_to_set
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
from real_estate_scraper.templates.sql.listing import listing_insert_query
from real_estate_scraper.templates.sql.error import error_insert_query
from models.property import Property


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


class SellersPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def __query_agent_data(self, agent_id):
        db = next(get_db())
        q = text(f"SELECT * FROM listings_agent WHERE agent_id = '{agent_id}';")
        result = db.execute(q)
        agent = result.fetchone()
        return agent

    def process_item(self, item, spider):
        # construct seller item
        seller_type = item["seller"]["seller_type"]
        registry_number = jmespath.search("seller.registry_number", item)
        if not seller_type:
            seller_type = "person"
        elif seller_type == "agency" and registry_number:
            # query agent data
            agent = self.__query_agent_data(registry_number)
            if agent:
                item["seller"]["agent_id"] = str(agent.id)
            else:
                item["seller"]["agent_id"] = None

        seller_name = jmespath.search("seller.name", item) or "Unknown Seller"
        seller_item = Seller(
            source_seller_id=jmespath.search("seller.source_seller_id", item),
            name=seller_name,
            seller_type=seller_type,
            primary_phone=jmespath.search("seller.primary_phone", item),
            primary_email=jmespath.search("seller.primary_email", item),
            website=jmespath.search("seller.website", item),
            agent_id=jmespath.search("seller.agent_id", item),
        )

        # Query the existing seller
        db = next(get_db())
        max_retries = 3
        for attempt in range(max_retries):
            try:
                q = text(
                    """
                    SELECT id FROM listings_seller 
                    WHERE source_seller_id = :source_seller_id
                    AND name = :name 
                    AND seller_type = :seller_type
                    LIMIT 1;
                """
                )
                item = {
                    "source_seller_id": str(seller_item.source_seller_id),
                    "name": seller_item.name,
                    "seller_type": seller_item.seller_type,
                }
                seller_id = db.execute(q, item).fetchone()
                seller_item.id = seller_id[0]
                break
            except psycopg2.OperationalError as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise
                db.close()
                db = next(get_db())  # Get fresh connection
                continue

        # if existing seller is exist
        if seller_item.id and seller_item.agent_id:
            q = text(
                f"""
                UPDATE listings_seller SET agent_id='{seller_item.agent_id}'
                WHERE id='{seller_item.id}';
                """
            )
            db.execute(q)
            db.commit()
            item["seller"]["id"] = str(seller_item.id)
            db.close()
            return item

        # execute query
        try:
            db.add(seller_item)
            db.commit()
            item["seller"]["id"] = str(seller_item.id)
        except Exception as err:
            db.rollback()
            raise ValueError("Seller insertion failed: {0}".format(err))
        finally:
            db.close()

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
            seller_id=item["seller"]["id"],
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
        # Query existing property
        db = next(get_db())
        existing_property = (
            db.query(Property).filter(Property.listing_id == item["listing_id"]).first()
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
            self.db.cursor.execute(q, property_item)
            self.db.conn.commit()
            item["property"]["id"] = str(property_item["id"])
        except Exception as err:
            db.rollback()
            # Insert error to db
            error = Error(
                url=item["url"],
                error_type="Property insertion",
                error_message=str(err),
                error_traceback=traceback.format_exc(),
            )
            db.add(error)
            db.commit()
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
            "raw_data_id",
        ]
        listing = self.db.cursor.fetchone()  # existing listing
        if not listing:
            spider.total_new_listings += 1
        elif listing:
            listing = dict(zip(columns, listing))
            previous_listing = PreviousListing(**listing)
            new_listing = PreviousListing(**item)
            # check the changes
            change_items = []
            for col in ["price", "short_description", "detail_description"]:
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
                    self.db.cursor.executemany(q, change_items)
                    self.db.conn.commit()
                    # convert the new_value to SET clause
                    new_values = {}
                    for change in change_items:
                        new_values.update({change[3]: change[5]})
                    if "price" in new_values and not new_values["price"]:
                        new_values["price"] = -1
                    set_clause = ", ".join([f"{k} = %s" for k in new_values.keys()])
                    # update the updated_at field on the listings table
                    listing_id = item["listing_id"]
                    q = f"""
                    UPDATE listings_listing SET updated_at=now(), {set_clause}
                    WHERE id='{listing_id}';
                    """
                    self.db.cursor.execute(q, list(new_values.values()))
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
