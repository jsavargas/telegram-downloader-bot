import asyncio
import os
import shutil
import time
from typing import Optional, Tuple

from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message

from logger_config import logger


class DownloadService:
    def __init__(
        self,
        env,
        utils,
        info_handler,
        command_handler,
        download_path_manager,
        pending_handler,
        file_data_handler,
        semaphore,
    ):
        self.env = env
        self.utils = utils
        self.info_handler = info_handler
        self.command_handler = command_handler
        self.download_path_manager = download_path_manager
        self.pending_handler = pending_handler
        self.file_data_handler = file_data_handler
        self.semaphore = semaphore

    async def process_message(self, message: Message, source_label: str = "Bot"):
        pending_key = message.id
        self.pending_handler.add_pending_message(pending_key, message)
        try:
            async with self.semaphore:
                await self._download_media(message, source_label=source_label)
        finally:
            self.pending_handler.remove_pending_message(pending_key, message)

    async def _download_media(self, message: Message, source_label: str):
        file_name = self.info_handler.getFileName(message)
        file_size = self.info_handler.getFileSize(message)
        origin_group = self.info_handler.get_originGroup_test(message)
        download_path = self.download_path_manager.getDownloadPath(message, origin_group, file_name)
        file_name = self.download_path_manager.getDownloadFilename(message, origin_group, file_name)

        start_time, start_hour = self.utils.startTime()
        temp_path = os.path.join(self.env.DOWNLOAD_INCOMPLETED_PATH, file_name)
        final_path = os.path.join(download_path, file_name)
        self.utils.create_folders(temp_path)
        self.utils.create_folders(final_path)

        summary = self._build_start_summary(
            file_name=file_name,
            download_path=download_path,
            start_hour=start_hour,
            file_size=file_size,
            origin_group=origin_group,
            source_label=source_label,
        )
        status_message = await self._create_status_message(message, summary)

        downloaded_path, retries = await self._download_with_retries(
            message=message,
            status_message=status_message,
            summary=summary,
            temp_path=temp_path,
            expected_size=file_size,
        )
        if not downloaded_path:
            if status_message:
                await status_message.edit_text(f"❌ Download failed: {file_name}")
            return

        temp_filename = self.command_handler.getTempFilename(None, message)
        if temp_filename:
            final_path = os.path.join(download_path, temp_filename)
            file_name = temp_filename

        final_path = self._resolve_duplicate(final_path, file_size)
        shutil.move(downloaded_path, final_path)
        self.utils.change_permissions(download_path)
        self.utils.change_permissions(final_path)
        self.file_data_handler.add_download_files(final_path, message)

        end_time, end_hour = self.utils.endTime()
        elapsed_time = max(self.utils.elapsedTime(start_time, end_time), 0.1)
        file_size_bytes, size_str = self.utils.getSize(final_path)
        download_speed_kb = file_size_bytes / elapsed_time / 1024

        download_info = {
            "file_name": file_name,
            "download_folder": download_path,
            "size_str": size_str,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "elapsed_time": elapsed_time,
            "download_speed": download_speed_kb,
            "origin_group": origin_group,
            "retries": retries,
            "message": message,
        }

        if status_message:
            await status_message.edit_text(self.utils.create_download_summary(download_info))
        if self.env.IS_DELETE:
            await message.delete()

    async def _download_with_retries(
        self,
        message: Message,
        status_message: Optional[Message],
        summary: str,
        temp_path: str,
        expected_size: Optional[int],
    ) -> Tuple[Optional[str], int]:
        attempts = 0
        while attempts < self.env.MAX_RETRIES:
            attempts += 1
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                callback = self._build_progress_callback(status_message, summary)
                downloaded = await message.download(
                    file_name=temp_path,
                    progress=callback if self.env.PROGRESS_DOWNLOAD else None,
                )
                if not downloaded:
                    raise RuntimeError("Empty download result")
                if expected_size and os.path.getsize(downloaded) != expected_size:
                    raise RuntimeError("Downloaded size mismatch")
                return downloaded, attempts - 1
            except FloodWait as e:
                wait_for = int(getattr(e, "value", 10)) + 1
                logger.warning(f"FloodWait during download, waiting {wait_for}s")
                await asyncio.sleep(wait_for)
            except RPCError as e:
                logger.warning(f"RPCError during download: {e}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Download attempt {attempts} failed: {e}")
                await asyncio.sleep(min(10, attempts * 2))
        return None, attempts

    async def _create_status_message(self, message: Message, text: str):
        try:
            return await message.reply_text(text, disable_web_page_preview=True)
        except Exception:
            try:
                return await message._client.send_message("me", text, disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"Cannot create status message: {e}")
                return None

    def _build_progress_callback(self, status_message: Optional[Message], base_summary: str):
        if not status_message:
            async def noop_callback(current, total):
                return
            return noop_callback

        state = {"last_percent": -1, "last_edit": 0.0, "start": time.monotonic()}
        percent_step = max(self.env.PROGRESS_PERCENT_STEP, 1)
        edit_interval = max(self.env.PROGRESS_EDIT_INTERVAL_SEC, 1)

        async def callback(current, total):
            if not total:
                return
            now = time.monotonic()
            percent = int((current / total) * 100)
            should_edit = (
                percent >= 100
                or percent - state["last_percent"] >= percent_step
            ) and (now - state["last_edit"] >= edit_interval or percent >= 100)
            if not should_edit:
                return
            state["last_percent"] = percent
            state["last_edit"] = now
            elapsed = max(now - state["start"], 0.1)
            speed_bps = current / elapsed
            speed_mbps = speed_bps / 1024 / 1024
            eta_seconds = int(max((total - current) / speed_bps, 0)) if speed_bps > 0 else 0
            progress_bar = self._progress_bar(percent)
            text = (
                f"{base_summary}\n\n"
                f"{progress_bar} `{percent}%`\n"
                f"⚡ `{speed_mbps:.2f} MB/s` · ⏳ `{eta_seconds}s`"
            )
            try:
                await status_message.edit_text(text, disable_web_page_preview=True)
            except Exception:
                return

        return callback

    def _build_start_summary(self, file_name, download_path, start_hour, file_size, origin_group, source_label):
        lines = [
            "🚀 **Download queued**",
            f"📦 **File:** `{file_name}`",
            f"📁 **Folder:** `{download_path}`",
            f"🧭 **Source:** `{source_label}`",
            f"🕒 **Start:** `{start_hour}`",
        ]
        if file_size:
            lines.append(f"📏 **Size:** `{self.utils.format_size(file_size)}`")
        if origin_group:
            lines.append(f"💬 **Origin:** `{origin_group}`")
        return "\n".join(lines)

    @staticmethod
    def _progress_bar(percent: int, size: int = 12) -> str:
        filled = int((percent / 100) * size)
        return "▰" * filled + "▱" * (size - filled)

    @staticmethod
    def _resolve_duplicate(final_path: str, expected_size: Optional[int]) -> str:
        if not os.path.exists(final_path):
            return final_path
        base, ext = os.path.splitext(final_path)
        index = 1
        suffix = "same_size_duplicate" if expected_size and os.path.getsize(final_path) == expected_size else "size_mismatch_duplicate"
        candidate = f"{base}_{suffix}_{index}{ext}"
        while os.path.exists(candidate):
            index += 1
            candidate = f"{base}_{suffix}_{index}{ext}"
        return candidate
