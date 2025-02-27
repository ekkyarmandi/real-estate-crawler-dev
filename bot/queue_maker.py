from telegram import Bot
from tqdm import tqdm
from database import get_db
from sqlalchemy import text
from models import CustomListing, User, Queue, Listing
from decouple import config
import asyncio

from datetime import datetime as dt

# city LISTING.city
# price LISTING.price
# size PROPERTY.size_m2
# rooms PROPERTY.rooms

# 🏢 City: [Belgrade] [[listing.city]]
# 📍 Location: [Serbia - City of Belgrade - Belgrade - Autokomanda - Admirala Vukovića] [[listing.city - listing.municipality - listing.micro_location]]
# 💰 Price: € [239,000] [[listing.price]]
# 📏 Size: [46] m² [[property.size_m2]]
# 🏠 Rooms: [2.0] [[property.rooms]]
# 📅 Publication date: [2024-11-30]
# 🔗 Link: [property.listing link]

# Load your bot token from environment variables
TOKEN = config("TELEGRAMBOT_TOKEN")

# Initialize the bot
bot = Bot(token=TOKEN)


async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print("Error sending message:", e)


def create_queue():
    db = next(get_db())
    today = dt.now().strftime(r"%Y-%m-%d")
    # users = db.query(User).all()
    users = [
        db.query(User).filter(User.id == "7c1c80ae-8634-405e-8e92-9340e42b37c1").first()
    ]
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
        AND ll.status = 'active' AND ll.url LIKE '%halooglasi.com%'
        ORDER BY ll.created_at DESC;
        """
    )
    results = db.execute(q)
    listings = results.fetchall()
    # convert raw data into custom listings
    listings = [dict(zip(cols, listing)) for listing in listings]
    listings = [CustomListing(**item) for item in listings]
    # send all the listings via telegram bot as notifications
    for user in users:
        user_queues = db.query(Queue.listing_id).filter(Queue.user_id == user.id).all()
        user_queues = [u[0] for u in user_queues]
        for l in tqdm(listings, desc="Adding to queue table"):
            if l.id not in user_queues and l.validate_settings(user.settings):
                # create queue
                queue = Queue(listing_id=l.id, user_id=user.id)
                try:
                    db.add(queue)
                    db.commit()
                except Exception:
                    db.rollback()


def main():
    db = next(get_db())
    user = db.query(User).filter(User.username == "ekkyarmandi").first()
    user_settings = user.settings_as_where_clause()
    # query listings that match with user settings
    cols = [
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
            listings.url,
            listings.city,
            listings.price,
            listings.municipality,
            listings.micro_location,
            properties.size_m2,
            properties.rooms
        FROM listings_listing as listings
        JOIN listings_property as properties ON listings.id = properties.listing_id
        WHERE {user_settings};
        """
    )
    r = db.execute(q)
    listing_item = dict(zip(cols, r.fetchone()))
    listing = CustomListing(**listing_item)
    # employ telegram bot for sending the message
    message = listing.as_markdown()
    asyncio.run(send_message(chat_id=user.chat_id, text=message))


if __name__ == "__main__":
    # main()
    create_queue()
