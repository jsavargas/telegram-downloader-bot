import os
from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_id_list(value):
    if not value:
        return []
    result = []
    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


class Env:
    def __init__(self):

        self.API_ID = os.getenv('TG_API_ID') or os.getenv('API_ID')
        self.API_HASH = os.getenv('TG_API_HASH') or os.getenv('API_HASH')
        self.BOT_TOKEN = os.getenv('TG_BOT_TOKEN') or os.getenv('BOT_TOKEN')
        self.USER_SESSION_STRING = os.getenv('TG_USER_SESSION_STRING') or os.getenv('USER_SESSION_STRING')
        self.ENABLE_USERBOT = _parse_bool(os.getenv('TG_ENABLE_USERBOT') or os.getenv('ENABLE_USERBOT'), False)
        self.MONITORED_CHAT_IDS = _parse_id_list(os.getenv('TG_MONITORED_CHAT_IDS') or os.getenv('MONITORED_CHAT_IDS'))
        # Handling both AUTHORIZED_USER_ID and TG_AUTHORIZED_USER_ID
        AUTHORIZED_USER_IDS = os.getenv('TG_AUTHORIZED_USER_ID') or os.getenv('AUTHORIZED_USER_ID', 'me')
        self.AUTHORIZED_USER_ID = AUTHORIZED_USER_IDS.replace(" ", "").split(",")
        self.PUID = _parse_int(os.getenv('PUID', '1001'), 1001)
        self.PGID = _parse_int(os.getenv('PGID', '1001'), 1001)

        self.MAX_CONCURRENT_TASKS = _parse_int(os.getenv('TG_MAX_PARALLEL') or os.getenv('MAX_CONCURRENT_TASKS', '3'), 3)
        self.WORKERS = _parse_int(os.getenv('WORKERS', '4'), 4)
        self.MAX_CONCURRENT_TRANSMISSIONS = _parse_int(os.getenv('MAX_CONCURRENT_TRANSMISSIONS', '4'), 4)
        self.MAX_RETRIES = _parse_int(os.getenv('MAX_RETRIES', '4'), 4)
        self.PROGRESS_STATUS_SHOW = _parse_int(os.getenv('PROGRESS_STATUS_SHOW', '10'), 10)
        self.PROGRESS_PERCENT_STEP = _parse_int(os.getenv('PROGRESS_PERCENT_STEP', '5'), 5)
        self.PROGRESS_EDIT_INTERVAL_SEC = _parse_int(os.getenv('PROGRESS_EDIT_INTERVAL_SEC', '6'), 6)

        self.IS_DELETE = _parse_bool(os.getenv('IS_DELETE', False), False)
        self.MESSAGE_FILE = os.getenv('MESSAGE_FILE', 'False').lower() in ('true', '1')
        self.PROGRESS_DOWNLOAD = os.getenv('PROGRESS_DOWNLOAD', 'True').strip().lower() in ('true', '1')

        self.CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config")
        self.DOWNLOAD_PATH = os.environ.get("DOWNLOAD_PATH", "/download")
        self.DOWNLOAD_COMPLETED_PATH = os.path.join(self.DOWNLOAD_PATH, "completed")
        self.DOWNLOAD_INCOMPLETED_PATH = os.path.join(self.DOWNLOAD_PATH, "incompleted")
        self.DOWNLOAD_PATH_TORRENTS = os.environ.get("DOWNLOAD_PATH_TORRENTS", "/watch")  # fmt: skip

        self.DOWNLOAD_FILES_DB = os.environ.get("DOWNLOAD_FILES_DB", os.path.join(self.CONFIG_PATH, "download_files_db.json"))  # fmt: skip
        self.PENDING_FILES_DB = os.environ.get("PENDING_FILES_DB", os.path.join(self.CONFIG_PATH, "pending_messages.json"))  # fmt: skip
        
        self.WELCOME="WELCOME"



    