# utils.py
import os

from pyrogram.types import Message

def format_file_size(file_size: int) -> str:
    if file_size < 1024:
        return f"{file_size} bytes"
    elif file_size < 1024 * 1024:
        return f"{file_size / 1024:.2f} KB"
    else:
        return f"{file_size / (1024 * 1024):.2f} MB"

def create_download_summary(download_info):
    """
    Creates a download summary message based on the download information.

    Args:
    - download_info (dict): Dictionary with the following structure:
        {
            'file_name': str,
            'size_str': str,
            'start_hour': str,
            'end_hour': str,
            'elapsed_time': float,
            'download_speed': float,
            'origin_group': str or None (optional)
        }
    
    Returns:
    - str: Formatted download summary message.
    """
    file_name = download_info['file_name']
    size_str = download_info['size_str']
    start_hour = download_info['start_hour']
    end_hour = download_info['end_hour']
    elapsed_time = download_info['elapsed_time']
    download_speed = download_info['download_speed']
    origin_group = download_info.get('origin_group', None)
    retries = download_info.get('retries', None)

    summary = (
        f"**Download completed**\n\n"
        f"**File Name:** {file_name}\n"
        f"**File Size:** {size_str}\n"
        f"**Start Time:** {start_hour}\n"
        f"**End Time:** {end_hour}\n"
        f"**Download Time:** {elapsed_time:.2f} seconds\n"
        f"**Download Speed:** {download_speed:.2f} KB/s"
    )

    if origin_group:
        summary += f"\n**Origin Group:** {origin_group}"
    if retries:
        summary += f"\n**Retries:** {retries}"


    return summary



def removeFiles():
    if os.path.exists("telegramBot" + ".session"): 
        os.remove("telegramBot" + ".session")