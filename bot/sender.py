from telegram import Bot
from decouple import config
from sqlalchemy import text
from database import get_db
from models import Queue, CustomListing
import asyncio
import logging

TOKEN = config("TELEGRAMBOT_TOKEN")
bot = Bot(token=TOKEN)

logger = logging.getLogger(__name__)


async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        print("Error sending message:", e)
        return False


async def send_queues():
    db = next(get_db())
    queues = (
        db.query(Queue)
        .filter(
            Queue.is_sent == False,
            Queue.user_id == "f4b4e969-3c29-478e-b793-607889842936",
        )
        .limit(30)
        .all()
    )
    count = 0
    for queue in queues:
        chat_id = queue.user.chat_id
        prop = queue.listing.property[0]
        listing_item = {
            "url": queue.listing.url,
            "city": queue.listing.city,
            "price": queue.listing.price,
            "municipality": queue.listing.municipality,
            "micro_location": queue.listing.micro_location,
            "size_m2": prop.size_m2,
            "rooms": prop.rooms,
        }
        listing = CustomListing(**listing_item)
        message = listing.as_markdown()

        # Send message and update queue if successful
        success = await send_message(chat_id=chat_id, text=message)
        if success:
            count += 1
            queue.is_sent = True
            db.commit()

    logger.info(f"{count} listings queued has been sent")


async def main():
    await send_queues()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
