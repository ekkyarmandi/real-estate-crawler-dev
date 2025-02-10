from telegram import Bot
from decouple import config
from database import get_db
from models import Queue, CustomListing
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import shutil

TOKEN = config("TELEGRAMBOT_TOKEN")
bot = Bot(token=TOKEN)

logger = logging.getLogger(__name__)

# Configure logging to write to a file with rotation
log_handler = RotatingFileHandler(
    "queue.log",  # Log file name
    maxBytes=1024 * 1024,  # Approximate size in bytes before rotating (e.g., 1MB)
    backupCount=5,  # Number of backup files to keep
)

# Optional: compress the rotated log files
log_handler.rotator = lambda source, dest: shutil.move(source, dest + ".gz")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        log_handler,
        logging.StreamHandler(),  # Optional: keep logging to console as well
    ],
)


async def send_message(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        print("Error sending message:", e)
        return False


async def send_queues():
    db = next(get_db())
    queues = db.query(Queue).filter(Queue.is_sent == False).limit(20).all()
    count = 0
    for queue in queues:
        chat_id = queue.user.chat_id
        prop = queue.listing.property
        if len(prop) == 0:
            continue
        prop = prop[0]
        listing_item = {
            "url": queue.listing.url,
            "city": queue.listing.city,
            "price": queue.listing.price,
            "municipality": queue.listing.municipality,
            "micro_location": queue.listing.micro_location,
            "size_m2": prop.size_m2,
            "rooms": prop.rooms,
            "first_seen_at": queue.listing.first_seen_at,
        }
        listing = CustomListing(**listing_item)
        if listing.has_missings():
            continue
        message = listing.as_markdown()

        # Send message and update queue if successful
        success = await send_message(chat_id=chat_id, text=message)
        if success:
            count += 1
            queue.is_sent = True
            db.commit()

    logger.info(f"{count} queued listings has been sent")


async def main():
    await send_queues()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
