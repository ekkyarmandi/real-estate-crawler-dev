# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from decouple import config
import dj_database_url
import psycopg2


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


class ListingPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        # construct listing data
        listing_item = dict(
            source_id=item["source_id"],
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
        # insert value
        q = """
        INSERT INTO listings_listing (
            id,
            source_id,
            url,
            title,
            short_description,
            detail_description,
            price,
            price_currency,
            status,
            created_at,
            updated_at,
            first_seen_at,
            last_seen_at,
            valid_from,
            valid_to,
            total_views,
            city,
            municipality,
            micro_location,
            latitude,
            longitude
        ) VALUES (
            uuid_generate_v4(),
            %(source_id)s,
            %(url)s,
            %(title)s,
            %(short_description)s,
            %(detail_description)s,
            %(price)s,
            %(price_currency)s,
            %(status)s,
            now(),
            now(),
            now(),
            now(),
            %(valid_from)s,
            %(valid_to)s,
            %(total_views)s,
            %(city)s,
            %(municipality)s,
            %(micro_location)s,
            %(latitude)s,
            %(longitude)s
        );
        """
        try:
            self.db.cursor.execute(q, listing_item)
            self.db.conn.commit()
        except Exception as err:
            print("Error inserting listing: {0}".format(err))
            self.db.conn.rollback()
        return item


class RawDataPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        return item


class ImagesPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        return item


class SourcesPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        return item


class SellersPipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        return item


class ListingChangePipeline:
    def __init__(self):
        self.db = PostgreSQLConnection()

    def process_item(self, item, spider):
        return item
