# import requests and database
import requests
from database import get_db
from sqlalchemy import text
from parsel import Selector
from tqdm import tqdm

# query and fetch all listings
db = next(get_db())
urls = db.execute(
    text(
        """
        SELECT ll.url FROM listings_listing ll
        JOIN listings_property lp ON ll.id = lp.listing_id
        WHERE ll.status = 'active' AND lp.rooms > 10
        AND ll.url LIKE '%halooglasi.com%';
        """
    )
).fetchall()
urls = [item[0] for item in urls]

# if the status code is not 200, mark status as 'removed'
for url in tqdm(urls):
    response = requests.get(url)
    if response.status_code != 200:
        db.execute(
            text(
                f"UPDATE listings_listing SET status = 'removed', updated_at=now() WHERE url='{url}'"
            )
        )
        db.commit()
