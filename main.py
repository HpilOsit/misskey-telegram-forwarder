import misskey
import utils
import logging
import telegram
import tempfile
from environs import Env
from datetime import *
from time import sleep
import asyncio


logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s',
                    level=logging.INFO)

env = Env()
# Read .env into os.environ
env.read_env()

TOKEN = env.str("BOT_TOKEN")
HOST = env.str("HOST", "https://misskey.io")
USERID = env.str("USERID")
CHANNEL_ID = env.str("CHANNEL_ID")
INTERVAL = env.int("INTERVAL", 300)

LATEST_NOTE_TIME = datetime.now().replace(tzinfo=timezone.utc)

bot = telegram.Bot(token=TOKEN)


async def get_medias(files, temp_dir):
    medias = []
    for file in files:
        if file["type"].startswith("image"):
            medias.append(
                telegram.InputMediaPhoto(
                    media=file["url"]
                )
            )
        elif file["type"].startswith("video"):
            try:
                transfered = await utils.transfer_video(file["url"], temp_dir)
            except:
                logging.error("Failed to transfer video. Falling back...")
                medias.append(
                telegram.InputMediaVideo(
                    file["url"]
                    )
                )
                continue

            vf = open(transfered, "rb")
            medias.append(
                telegram.InputMediaVideo(
                    vf
                )
            )
        else:
            medias.append(
                telegram.InputMediaDocument(
                    media=file["url"]
                )
            )
    return medias


async def forward_new_notes(bot: telegram.Bot):
    global LATEST_NOTE_TIME
    notes = misskey.get_notes(
        site=HOST,
        user_id=USERID,
    )
    # forward new notes
    for n in reversed(notes):
        if n.createdAt > LATEST_NOTE_TIME:
            # forward
            if len(n.files) == 0:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=n.text,
                    parse_mode=telegram.constants.ParseMode("HTML")
                )
                logging.info(
                    f"Forwarded a text note, content: {n.text[:10]}...")
            else:
                with tempfile.TemporaryDirectory() as temp_dir:
                    medias = await get_medias(n.files, temp_dir)
                    try:
                        await bot.send_media_group(
                            chat_id=CHANNEL_ID,
                            media=medias,
                            caption=n.text,
                            parse_mode=telegram.constants.ParseMode("HTML"),
                        )
                    except asyncio.TimeoutError:
                        logging.error("Send media group timeout!")
                        continue
                    logging.info(
                        f"Forwarded a note with media, content: {n.text[:10]}... with {len(medias)} medias")
                LATEST_NOTE_TIME = n.createdAt


async def main():
    logging.info("----- Bot started -----")
    while True:
        await forward_new_notes(bot)
        sleep(INTERVAL)
    logging.info("----- Bot stopped -----")


if __name__ == "__main__":
    asyncio.run(main())
