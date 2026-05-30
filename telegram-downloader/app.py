# -*- coding: utf-8 -*-
import asyncio
import os
import re
import time
from datetime import datetime

import yt_dlp
from pyrogram import Client, filters, idle, __version__ as pyrogram_version
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, Message

from command_handler import CommandHandler
from data_handler import FileDataHandler
from downloadPathManager import DownloadPathManager
from download_service import DownloadService
from env import Env
from info_handler import InfoMessages
from logger_config import logger
from pending_handler import PendingMessagesHandler
from print_handler import PartialPrinter
from url_downloader import URLDownloader
from utils import Utils

logger.info(f"Starting Telegram Downloader Bot Started : {datetime.now():%Y/%m/%d %H:%M:%S}")


class Config:
    def __init__(self):
        self.BOT_VERSION = "1.1.0-r1"
        self.PYROGRAM_VERSION = pyrogram_version
        self.YT_DLP_VERSION = yt_dlp.version.__version__


config = Config()
env = Env()
utils = Utils()
print_handler = PartialPrinter()
download_files_db = FileDataHandler()
download_path_manager = DownloadPathManager()
command_handler = CommandHandler(config)
url_downloader = URLDownloader()
pending_messages_handler = PendingMessagesHandler()
info_handler = InfoMessages()
semaphore = asyncio.Semaphore(int(env.MAX_CONCURRENT_TASKS))
download_service = DownloadService(
    env=env,
    utils=utils,
    info_handler=info_handler,
    command_handler=command_handler,
    download_path_manager=download_path_manager,
    pending_handler=pending_messages_handler,
    file_data_handler=download_files_db,
    semaphore=semaphore,
)

utils.removeFiles()

bot_app = Client(
    "telegramBot",
    api_id=int(env.API_ID),
    api_hash=env.API_HASH,
    bot_token=env.BOT_TOKEN,
    workers=env.WORKERS,
    max_concurrent_transmissions=env.MAX_CONCURRENT_TRANSMISSIONS,
)

user_app = None
if env.ENABLE_USERBOT and env.USER_SESSION_STRING:
    user_app = Client(
        "telegramUser",
        api_id=int(env.API_ID),
        api_hash=env.API_HASH,
        session_string=env.USER_SESSION_STRING,
        workers=env.WORKERS,
        max_concurrent_transmissions=env.MAX_CONCURRENT_TRANSMISSIONS,
    )

MEDIA_FILTER = filters.document | filters.photo | filters.video | filters.audio | filters.animation


def message2file(message: Message):
    if not env.MESSAGE_FILE:
        return False
    with open(os.path.join(env.CONFIG_PATH, "messages.txt"), "a", encoding="utf-8") as file:
        file.write(f"MESSAGE_FILE:: {datetime.now():%Y/%m/%d %H:%M:%S}\n{message}\n\n\n\n")
    return True


def is_authorized(message: Message) -> bool:
    user_id = info_handler.get_userId(message)
    if user_id and str(user_id) in env.AUTHORIZED_USER_ID:
        return True
    if message.chat and message.chat.id in env.MONITORED_CHAT_IDS:
        return True
    return False


async def handle_media_download(message: Message, source_label: str):
    message2file(message)
    await download_service.process_message(message, source_label=source_label)


@bot_app.on_message(MEDIA_FILTER)
async def handle_bot_media(client: Client, message: Message):
    if not is_authorized(message):
        return
    await handle_media_download(message, source_label="Bot")


@bot_app.on_message(filters.command(command_handler.command_keys))
async def handle_commands(client: Client, message: Message):
    if not message.from_user:
        return
    if str(message.from_user.id) not in env.AUTHORIZED_USER_ID and message.command[0] != "id":
        return
    message2file(message)
    await command_handler.process_command(client, message)


@bot_app.on_message(filters.text)
async def handle_text_messages(client: Client, message: Message):
    if not is_authorized(message):
        return
    url_regex = re.compile(r"https?://\S+")
    urls = url_regex.findall(message.text or "")
    if not urls:
        return
    async with semaphore:
        for url in urls:
            await url_downloader.download_from_url(client, message, url)


@bot_app.on_callback_query(filters.regex(r"^ytdown_.*"))
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    await url_downloader.handle_callback_query(client, callback_query)


if user_app:
    @user_app.on_message(MEDIA_FILTER)
    async def handle_user_media(client: Client, message: Message):
        if not message.chat or message.chat.id not in env.MONITORED_CHAT_IDS:
            return
        await handle_media_download(message, source_label="UserBot")


def announce_start():
    msg_txt = (
        "Telegram Downloader started\n\n"
        f"bot version: {config.BOT_VERSION}\n"
        f"pyrogram version: {pyrogram_version}\n"
        f"yt_dlp version: {yt_dlp.version.__version__}\n"
        f"userbot enabled: {bool(user_app)}\n"
        f"monitored chats: {len(env.MONITORED_CHAT_IDS)}"
    )
    logger.info(msg_txt)
    print_handler.print_variable("BOT_VERSION", config.BOT_VERSION)
    print_handler.print_variable("PYROGRAM_VERSION", pyrogram_version)
    print_handler.print_variable("YTDLP_VERSION", yt_dlp.version.__version__)
    print_handler.print_variable("USERBOT_ENABLED", bool(user_app))
    print_handler.print_variable("MONITORED_CHAT_IDS", env.MONITORED_CHAT_IDS)
    print_handler.print_variables()
    numeric_user_ids = [user_id for user_id in env.AUTHORIZED_USER_ID if str(user_id).isdigit()]
    if numeric_user_ids:
        try:
            bot_app.send_message(int(numeric_user_ids[0]), msg_txt)
        except Exception as e:
            logger.warning(f"Cannot send startup message: {e}")
    else:
        logger.info("Startup message skipped: no numeric AUTHORIZED_USER_ID configured")


def start_clients():
    while True:
        try:
            bot_app.start()
            if user_app:
                user_app.start()
            announce_start()
            idle()
            break
        except FloodWait as e:
            wait_for = int(getattr(e, "value", 30)) + 5
            logger.warning(f"FloodWait while starting clients. Retrying in {wait_for}s")
            time.sleep(wait_for)
        finally:
            try:
                bot_app.stop()
            except Exception:
                pass
            if user_app:
                try:
                    user_app.stop()
                except Exception:
                    pass


if __name__ == "__main__":
    start_clients()
