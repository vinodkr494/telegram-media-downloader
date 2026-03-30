import asyncio
import os
import sys
import json
import traceback
from telethon import TelegramClient
from telethon.tl.types import (
    InputMessagesFilterPhotos,
    InputMessagesFilterVideo,
    InputMessagesFilterDocument,
    InputMessagesFilterMusic,
    InputMessagesFilterUrl,
    InputMessagesFilterGif,
    MessageMediaPhoto,
    MessageMediaDocument
)

STATE_FILE = "download_state.json"
TASKS_FILE = "active_tasks.json"

def load_active_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tasks: {e}")
            return []
    return []

def save_active_tasks(tasks):
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(tasks, f)
    except Exception as e:
        print(f"Error saving tasks: {e}")

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
    original_input = str(channel_input).strip()
    
    # Pre-processing: aggressively normalize numeric channel IDs
    if original_input.isdigit() or (original_input.startswith("-") and original_input[1:].isdigit()):
        clean_id = original_input.replace("-", "")
        
        # If the user included the '100' prefix but forgot the negative sign: 1001553086349
        if clean_id.startswith("100") and len(clean_id) >= 12:
            channel_input = int(f"-{clean_id}")
        # If the user provided the raw short ID: 1553086349
        elif not original_input.startswith("-") and len(original_input) >= 8:
            channel_input = int(f"-100{original_input}")
        else:
            # It was either correctly formatted like -1001553086349 or it's a small group ID
            channel_input = int(original_input)
            
        # Update original_input so fallback search uses the perfectly normalized -100... format
        original_input = str(channel_input)
            
    try:
        # First attempt: direct get_entity
        channel = await client.get_entity(channel_input)
        return channel
    except Exception as e:
        # Second attempt: if direct lookup fails (common for private entities),
        # try to find it in ALL dialogs of the current user.
        print(f"Direct lookup for {original_input} failed ({e}). Searching through dialogs... this may take a moment.")
        active_count = 0
        archived_count = 0
        try:
            # Check Active Dialogs
            async for dialog in client.iter_dialogs():
                active_count += 1
                d_id = str(dialog.id)
                o_id = str(original_input)
                if d_id == o_id or d_id.replace("-100", "", 1) == o_id.replace("-100", "", 1):
                    print(f"Found entity in active dialogs (checked {active_count}): {dialog.title}")
                    return dialog.entity
                    
            # Check Archived Dialogs
            print(f"Not in active dialogs (checked {active_count}). Searching archived dialogs...")
            async for dialog in client.iter_dialogs(archived=True):
                archived_count += 1
                d_id = str(dialog.id)
                o_id = str(original_input)
                if d_id == o_id or d_id.replace("-100", "", 1) == o_id.replace("-100", "", 1):
                    print(f"Found entity in archived dialogs (checked {archived_count}): {dialog.title}")
                    return dialog.entity
                    
            print(f"Channel {original_input} was completely missing from all {active_count} active and {archived_count} archived chats.")
        except Exception as dialog_err:
            print(f"Dialog search also failed: {dialog_err}")
                 
        # Final attempt: if it's numeric and it failed, maybe try adding -100 if it lacks it
        if isinstance(channel_input, int) and channel_input > 0 and not str(channel_input).startswith("-100"):
            try:
                alt_id = int(f"-100{channel_input}")
                channel = await client.get_entity(alt_id)
                return channel
            except: pass
            
        error_msg = f"Telegram completely declined access to {channel_input}."
        if "Could not find the input entity" in str(e):
            error_msg += (
                f"\n\nWe scanned all {active_count} active and {archived_count} archived dialogs on this account, and the ID {original_input} is not among them."
                f"\n\nTo fix this:\n1. Open the channel on your phone to refresh it to the top of your chat list.\n2. Ensure you are logged into the correct Telegram account covering these chats.\n3. OR bypass this entirely by pasting the invite link (https://t.me/...) into the search bar."
            )
            
        raise Exception(error_msg) # Re-raise with the helpful tip
import time

async def download_single_file(client, channel, message, folder_name, progress_cb=None, complete_cb=None, cancel_event=None, max_speed_kb=None):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            file_size = (
                message.video.size if getattr(message, 'video', None)
                else message.document.size if getattr(message, 'document', None) 
                else message.audio.size if getattr(message, 'audio', None)
                else getattr(message, 'size', 0)
            )
            
            # Deduplication Check
            file_name = None
            if getattr(message, 'file', None):
                file_name = message.file.name or f"{message.file.id}{message.file.ext}"
            
            if file_name:
                expected_filepath = os.path.join(folder_name, file_name)
                if os.path.exists(expected_filepath):
                    existing_size = os.path.getsize(expected_filepath)
                    if file_size and existing_size == file_size:
                        if progress_cb:
                            progress_cb(message.id, existing_size, existing_size, speed_str="Skipped (Exists)")
                        if complete_cb:
                            complete_cb(message.id, filepath=expected_filepath)
                        return

            # Speed tracking variables
            start_time = [time.time()]
            last_bytes = [0]
            cancelled_by_event = [False]
            
            class PauseRequested(Exception): pass
            
            async def internal_progress(current, total):
                if cancel_event and cancel_event.is_set():
                    raise PauseRequested()
                
                now = time.time()
                elapsed = now - start_time[0]
                if elapsed >= 0.1:
                    bytes_diff = current - last_bytes[0]
                    speed_kb_s = (bytes_diff / elapsed) / 1024
                    
                    if max_speed_kb and speed_kb_s > max_speed_kb:
                        expected_time = (bytes_diff / 1024) / max_speed_kb
                        sleep_time = expected_time - elapsed
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                            now = time.time()
                            elapsed = now - start_time[0]
                            speed_kb_s = (bytes_diff / elapsed) / 1024

                    speed_str = f"{(speed_kb_s/1024):.1f} MB/s" if speed_kb_s > 1024 else f"{int(speed_kb_s)} KB/s"
                    start_time[0] = now
                    last_bytes[0] = current
                    if progress_cb:
                        progress_cb(message.id, current, total or file_size, speed_str=speed_str)

            dir_path = os.path.join(folder_name, "")
            file_path = None
            try:
                file_path = await message.download_media(
                    file=dir_path,
                    progress_callback=internal_progress,
                )
            except PauseRequested:
                if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                return
            except AttributeError as attr_err:
                if "location" in str(attr_err) and getattr(message, 'photo', None):
                    # Fallback for Telethon 1.38.x PhotoSize bug
                    from telethon.tl.types import InputPhotoFileLocation
                    photo = message.photo
                    # Pick largest size that isn't empty
                    best_size = None
                    if photo.sizes:
                        # Just grab the last one that has a type
                        for sz in reversed(photo.sizes):
                            if hasattr(sz, 'type'):
                                best_size = sz
                                break
                    
                    if best_size:
                        loc = InputPhotoFileLocation(
                            id=photo.id,
                            access_hash=photo.access_hash,
                            file_reference=photo.file_reference,
                            thumb_size=best_size.type
                        )
                        fname = f"Photo_{message.id}.jpg"
                        file_path = os.path.join(folder_name, fname)
                        try:
                            await client.download_file(
                                loc,
                                file=file_path,
                                progress_callback=internal_progress,
                            )
                        except PauseRequested:
                            if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                            return
                    else: raise
                else: raise

            if complete_cb:
                complete_cb(message.id, filepath=file_path)
            break

        except asyncio.CancelledError:
            if complete_cb: complete_cb(message.id, paused=True, filepath=None)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = getattr(e, 'seconds', 2)
                print(f"Error downloading {message.id}, retrying in {wait_time}s ({attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(wait_time)
                if client and channel:
                    try:
                        refreshed = await client.get_messages(channel, ids=message.id)
                        if refreshed: message = refreshed
                    except: pass
            else:
                print(f"Error downloading message {message.id} after {max_retries} attempts: {e}")
                if complete_cb: complete_cb(message.id, paused=False)

async def download_in_batches_headless(client, channel, messages, folder_name, batch_size, downloaded_state, progress_cb, complete_cb, task_cancel_event=None, max_speed_kb=None):
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
            await download_single_file(client, channel, message, folder_name, progress_cb, internal_complete, task_cancel_event, max_speed_kb)

    tasks = [download_message(m) for m in messages if m.id not in downloaded_state]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def get_messages_by_type(client, channel, media_choice, min_id=None, max_id=None, limit=2000):
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
        
    kwargs = {"limit": limit}
    if filter_type: kwargs["filter"] = filter_type
    if min_id: kwargs["min_id"] = min_id
    if max_id: kwargs["max_id"] = max_id

    messages = await client.get_messages(channel, **kwargs)
    
    # Post-filtering for document types
    if media_choice == 3:
        messages = [m for m in messages if m.document and m.document.mime_type == "application/pdf"]
    elif media_choice == 4:
        messages = [m for m in messages if m.document and m.document.mime_type == "application/zip"]
    elif media_choice == 5:
        messages = [m for m in messages if m.document and m.document.mime_type.startswith("audio/")]
        
    return messages

async def fetch_categorized_media(client, channel, limit=500):
    """
    Fetches up to `limit` messages for each distinct media category IN PARALLEL.
    All 6 filters run simultaneously via asyncio.gather, ~5x faster than sequential.
    Returns a dict: {"Media": [...], "Files": [...], "Music": [...], "Links": [...], "GIFs": [...]}
    """
    (photos, videos, files, music, links, gifs) = await asyncio.gather(
        client.get_messages(channel, filter=InputMessagesFilterPhotos(), limit=limit),
        client.get_messages(channel, filter=InputMessagesFilterVideo(), limit=limit),
        client.get_messages(channel, filter=InputMessagesFilterDocument(), limit=limit),
        client.get_messages(channel, filter=InputMessagesFilterMusic(), limit=limit),
        client.get_messages(channel, filter=InputMessagesFilterUrl(), limit=limit),
        client.get_messages(channel, filter=InputMessagesFilterGif(), limit=limit),
    )

    return {
        "Media": sorted(list(photos) + list(videos), key=lambda m: m.id, reverse=True)[:limit],
        "Files": list(files),
        "Music": list(music),
        "Links": list(links),
        "GIFs":  list(gifs),
    }

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
