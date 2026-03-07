import asyncio
import os
import sys
import json
from telethon import TelegramClient
from telethon.tl.types import (
    InputMessagesFilterVideo,
    InputMessagesFilterPhotos,
    InputMessagesFilterDocument,
)

STATE_FILE = "download_state.json"

def load_download_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error loading state: {e}")
            return set()
    return set()

def save_download_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(list(state), f)
    except Exception as e:
        print(f"Error saving state: {e}")

async def fetch_channel(client, channel_input):
    """
    Fetch a channel by username or ID.
    If input is pure digits or starts with -100, treat as integer ID.
    """
    if str(channel_input).startswith("-100") or str(channel_input).isdigit():
        channel_input = int(channel_input)
    
    channel = await client.get_entity(channel_input)
    return channel
import time

async def download_single_file(message, folder_name, progress_cb=None, complete_cb=None, cancel_event=None):
    try:
        file_size = (
            message.video.size if getattr(message, 'video', None)
            else message.document.size if getattr(message, 'document', None) 
            else message.audio.size if getattr(message, 'audio', None)
            else getattr(message, 'size', 0)
        )
        
        # Speed tracking variables
        start_time = [time.time()]
        last_bytes = [0]
        
        def internal_progress(current, total):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError("Download Paused")
            
            now = time.time()
            elapsed = now - start_time[0]
            speed_str = "0 KB/s"
            
            # Update speed every 0.5s to avoid jitter
            if elapsed >= 0.5:
                bytes_diff = current - last_bytes[0]
                speed_kb_s = (bytes_diff / elapsed) / 1024
                
                if speed_kb_s > 1024:
                    speed_str = f"{(speed_kb_s/1024):.1f} MB/s"
                else:
                    speed_str = f"{sys.maxsize if speed_kb_s < 0 else int(speed_kb_s)} KB/s" if speed_kb_s < 0 else f"{int(speed_kb_s)} KB/s"
                
                start_time[0] = now
                last_bytes[0] = current

            if progress_cb:
                # telethon total could be None
                progress_cb(message.id, current, total or file_size, speed_str=speed_str)

        dir_path = os.path.join(folder_name, "") # Enforce trailing slash for Telethon directory matching
        file_path = await message.download_media(
            file=dir_path,
            progress_callback=internal_progress,
        )
        if complete_cb:
            complete_cb(message.id, filepath=file_path)
            
    except asyncio.CancelledError:
        print(f"Download paused for message {message.id}")
        if complete_cb:
            complete_cb(message.id, paused=True, filepath=None)
    except Exception as e:
        print(f"Error downloading message {message.id}: {e}")
        if complete_cb:
            complete_cb(message.id, paused=False) # Marked as complete to not block pipeline

async def download_in_batches_headless(messages, folder_name, batch_size, downloaded_state, progress_cb, complete_cb, task_cancel_event=None):
    semaphore = asyncio.Semaphore(batch_size)
    
    def internal_complete(msg_id, paused=False, filepath=None):
        if not paused:
            downloaded_state.add(msg_id)
            save_download_state(downloaded_state)
        if complete_cb:
            complete_cb(msg_id, paused=paused, filepath=filepath)

    async def download_message(message):
        async with semaphore:
            if task_cancel_event and task_cancel_event.is_set():
                if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                return
            await download_single_file(message, folder_name, progress_cb, internal_complete, task_cancel_event)

    tasks = [download_message(m) for m in messages if m.id not in downloaded_state]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def get_messages_by_type(client, channel, media_choice, limit=2000):
    """
    media_choice: 
    1 - Images
    2 - Videos
    3 - PDFs
    4 - ZIP files
    5 - Audio files
    6 - All Media
    """
    filter_type = None
    if media_choice == 1:
        filter_type = InputMessagesFilterPhotos()
    elif media_choice == 2:
        filter_type = InputMessagesFilterVideo()
    elif media_choice in [3, 4, 5]:
        filter_type = InputMessagesFilterDocument()
    else:
        filter_type = None # All media
        

    messages = await client.get_messages(channel, filter=filter_type, limit=limit)
    
    # Post-filtering for document types
    if media_choice == 3:
        messages = [m for m in messages if m.document and m.document.mime_type == "application/pdf"]
    elif media_choice == 4:
        messages = [m for m in messages if m.document and m.document.mime_type == "application/zip"]
    elif media_choice == 5:
        # Audio
        messages = [m for m in messages if m.document and m.document.mime_type.startswith("audio/")]
        
    return messages

def get_folder_name(media_choice):
    folders = {
        1: "images",
        2: "videos",
        3: "pdfs",
        4: "zips",
        5: "audio",
        6: "all_media"
    }
    return f"downloads/{folders.get(media_choice, 'all_media')}"
