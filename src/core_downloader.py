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
    InputMessagesFilterVoice,
    InputMessagesFilterRoundVideo,
    MessageMediaPhoto,
    MessageMediaDocument
)
from database import save_task_db, load_active_tasks_db, remove_task_db, cache_media_list, mark_media_completed, get_completed_state_db
from utils.file_utils import get_media_filename
from utils.fast_telethon import fast_download_file, _atomic_finalize_sync

def load_active_tasks():
    return load_active_tasks_db()

def save_active_tasks(tasks):
    # Sync with SQLite by first deleting all tasks in the DB
    try:
        import sqlite3
        from database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error syncing active tasks to DB: {e}")

    # For backward compatibility, keep the loop but save each to DB
    for t in tasks:
        save_task_db(t)

def load_download_state(channel_id=None):
    # We return a set of msg_ids for a specific channel to ensure ID isolation
    if not channel_id:
        return set()
    res = get_completed_state_db()
    c_id = str(channel_id).replace("-100", "", 1)
    return {msg_id for ch_id, msg_id in res if ch_id == c_id}

def save_download_state(state):
    # This is usually called file-by-file in the worker via complete_cb
    # but if called globally, we can't easily map to channels here.
    # We recommend using mark_media_completed instead.
    pass

def parse_channel_input(channel_input):
    """
    Parses channel input which might contain a topic ID in 'channelID_topicID' format
    or a Telegram URL with a topic ID (e.g., t.me/c/123456789/1).
    Returns (clean_channel_input, topic_id).
    """
    s = str(channel_input).strip()
    
    # 0. Handle web.telegram.org format (Web A, Web K, Web Z formats)
    if "web.telegram.org" in s:
        try:
            if "#" in s:
                fragment = s.split("#")[-1]
                # Extract value from query param p= if present (common in Web K/Z)
                if "p=" in fragment:
                    p_val = fragment.split("p=")[-1].split("&")[0]
                    fragment = p_val
                
                # Strip leading 'c' if it's followed by digits (e.g., c123456789 -> 123456789)
                if fragment.startswith("c"):
                    cleaned_part = fragment[1:].replace("-", "").split("_")[0]
                    if cleaned_part.isdigit():
                        fragment = fragment[1:]
                
                # If there's a topic/message ID separator '_'
                if "_" in fragment:
                    parts = fragment.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        return parts[0], int(parts[1])
                s = fragment
        except: pass

    # 1. Handle URL format: https://t.me/c/123456789/1
    if "t.me/c/" in s:
        try:
            # Extract the part after /c/
            parts = s.split("t.me/c/")[-1].split("/")
            if len(parts) >= 2:
                chan_id = parts[0]
                topic_id = parts[1]
                if topic_id.isdigit():
                    # Prefix with -100 if it's a numeric ID
                    if chan_id.isdigit() and not chan_id.startswith("-"):
                        chan_id = f"-100{chan_id}"
                    return chan_id, int(topic_id)
        except: pass

    # 2. Handle ID_topicID format: -100123456789_123
    if "_" in s:
        parts = s.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            # Basic validation that parts[0] looks like a channel ID or username
            return parts[0], int(parts[1])
            
    return s, None

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
        title = getattr(channel, 'title', getattr(channel, 'username', getattr(channel, 'first_name', 'Unknown')))
        print(f"DEBUG: Successfully resolved channel/entity: '{title}' (ID: {channel.id})")
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

def get_unique_filepath(folder, filename, reserved_paths=None):
    os.makedirs(folder, exist_ok=True)
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    new_filepath = os.path.join(folder, new_filename)

    def is_occupied(path):
        # 1. Check in-memory reservation for concurrent downloads
        if reserved_paths is not None and (path in reserved_paths or (path + ".part") in reserved_paths):
            return True
        # 2. Check if file exists on disk with content > 0 bytes
        if os.path.exists(path):
            try:
                if os.path.getsize(path) > 0:
                    return True
            except Exception:
                return True
        # 3. Check if active/in-progress .part file exists on disk with content > 0 bytes
        if os.path.exists(path + ".part"):
            try:
                if os.path.getsize(path + ".part") > 0:
                    return True
            except Exception:
                return True
        return False

    while is_occupied(new_filepath):
        counter += 1
        new_filename = f"{base} ({counter}){ext}"
        new_filepath = os.path.join(folder, new_filename)

    if reserved_paths is not None:
        reserved_paths.add(new_filepath)

    return new_filepath

async def download_single_file(client, channel, message, folder_name, progress_cb=None, complete_cb=None, cancel_event=None, max_speed_kb=None, reserved_paths=None):
    from ui.views.settings_view import load_config
    cfg = load_config()
    rename_duplicates = cfg.get("rename_duplicates", True)
    use_message_date = cfg.get("use_message_date", True)
    prefix_file_date = cfg.get("prefix_file_date", True)

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
            file_name = get_media_filename(message, prefix_date=prefix_file_date)
            
            expected_filepath = None
            if file_name:
                from telethon.utils import get_peer_id
                from database import get_media_downloaded_path, update_media_downloaded_path
                c_id = str(get_peer_id(channel)).replace("-100", "", 1)
                
                db_filename = get_media_downloaded_path(c_id, message.id) if rename_duplicates else None
                if db_filename:
                    candidate_filepath = os.path.join(folder_name, db_filename)
                    # Check if this exact file or its .part exists on disk
                    if os.path.exists(candidate_filepath) or os.path.exists(candidate_filepath + ".part"):
                        expected_filepath = candidate_filepath
                    else:
                        expected_filepath = get_unique_filepath(folder_name, file_name, reserved_paths=reserved_paths)
                        update_media_downloaded_path(c_id, message.id, os.path.basename(expected_filepath))
                else:
                    candidate_filepath = os.path.join(folder_name, file_name)
                    if rename_duplicates:
                        is_candidate_reserved = reserved_paths is not None and (candidate_filepath in reserved_paths or (candidate_filepath + ".part") in reserved_paths)
                        if (os.path.exists(candidate_filepath) or os.path.exists(candidate_filepath + ".part")) and not is_candidate_reserved:
                            expected_filepath = candidate_filepath
                        else:
                            expected_filepath = get_unique_filepath(folder_name, file_name, reserved_paths=reserved_paths)
                        update_media_downloaded_path(c_id, message.id, os.path.basename(expected_filepath))
                    else:
                        expected_filepath = candidate_filepath

                if reserved_paths is not None:
                    reserved_paths.add(expected_filepath)
            
            if expected_filepath:
                # 1. Target file already completely exists
                if os.path.exists(expected_filepath):
                    existing_size = os.path.getsize(expected_filepath)
                    if file_size and existing_size >= file_size:
                        # Clean up any leftover orphaned .part or .meta files
                        part_path = expected_filepath + ".part"
                        meta_path = expected_filepath + ".part.meta"
                        if os.path.exists(part_path):
                            try: os.remove(part_path)
                            except Exception: pass
                        if os.path.exists(meta_path):
                            try: os.remove(meta_path)
                            except Exception: pass
                        if progress_cb:
                            progress_cb(message.id, existing_size, existing_size, speed_str="Skipped (Exists)")
                        if complete_cb:
                            complete_cb(message.id, filepath=expected_filepath)
                        return

                # 2. Check if .part file is genuinely fully downloaded and can be finalized
                part_path = expected_filepath + ".part"
                meta_path = expected_filepath + ".part.meta"
                if os.path.exists(part_path) and file_size and os.path.getsize(part_path) == file_size:
                    can_finalize = False
                    if file_size > 1024 * 1024 or os.path.exists(meta_path):
                        # Chunked download: MUST verify with metadata that all chunks were completed
                        if os.path.exists(meta_path):
                            from utils.fast_telethon import CHUNK_SIZE, _load_meta
                            import math
                            total_parts = math.ceil(file_size / CHUNK_SIZE)
                            completed_parts = _load_meta(meta_path, file_size, total_parts)
                            if total_parts > 0 and len(completed_parts) == total_parts:
                                can_finalize = True
                    else:
                        # Non-chunked small file where size matches
                        can_finalize = True

                    if can_finalize and _atomic_finalize_sync(part_path, expected_filepath, meta_path):
                        if progress_cb:
                            progress_cb(message.id, file_size, file_size, speed_str="Complete")
                        if complete_cb:
                            complete_cb(message.id, filepath=expected_filepath)
                        return

            # Speed tracking variables
            start_time = [time.time()]
            last_bytes = [0]
            is_first_cb = [True]
            smoothed_speed = [0.0]
            
            class PauseRequested(Exception): pass
            
            async def internal_progress(current, total):
                if cancel_event and cancel_event.is_set():
                    raise PauseRequested()
                
                tot = total or file_size or 0
                if is_first_cb[0]:
                    is_first_cb[0] = False
                    last_bytes[0] = current
                    start_time[0] = time.time()
                    if progress_cb:
                        initial_status = "Resuming..." if current > 0 else "Starting..."
                        progress_cb(message.id, current, tot, speed_str=initial_status)
                    return

                now = time.time()
                elapsed = now - start_time[0]
                if elapsed >= 0.2:
                    bytes_diff = current - last_bytes[0]
                    instant_speed_kb_s = (bytes_diff / elapsed) / 1024 if elapsed > 0 else 0.0
                    
                    if max_speed_kb and instant_speed_kb_s > max_speed_kb:
                        expected_time = (bytes_diff / 1024) / max_speed_kb
                        sleep_time = expected_time - elapsed
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                            now = time.time()
                            elapsed = now - start_time[0]
                            instant_speed_kb_s = (bytes_diff / elapsed) / 1024 if elapsed > 0 else 0.0

                    # Exponential Moving Average for silky smooth speed output
                    if smoothed_speed[0] <= 0.0:
                        smoothed_speed[0] = instant_speed_kb_s
                    else:
                        smoothed_speed[0] = 0.7 * smoothed_speed[0] + 0.3 * instant_speed_kb_s

                    speed_val = smoothed_speed[0]
                    speed_str = f"{(speed_val/1024):.1f} MB/s" if speed_val > 1024 else f"{int(speed_val)} KB/s"
                    start_time[0] = now
                    last_bytes[0] = current
                    if progress_cb:
                        progress_cb(message.id, current, tot, speed_str=speed_str)

            dir_path = os.path.join(folder_name, "")
            target_path = expected_filepath if file_name else dir_path
            
            file_path = None

            # 🚀 Strategy 0: High-Speed FastTelethon Parallel Chunk Downloader for files > 1MB
            if file_size and file_size > 1024 * 1024 and expected_filepath:
                try:
                    target_obj = getattr(message, 'media', None) or getattr(message, 'document', None) or getattr(message, 'video', None) or message
                    if target_obj:
                        success = await fast_download_file(
                            client=client,
                            location=target_obj,
                            target_path=expected_filepath,
                            file_size=file_size,
                            progress_callback=internal_progress,
                            cancel_event=cancel_event,
                            workers=4
                        )
                        if success and os.path.exists(expected_filepath):
                            file_path = expected_filepath
                except PauseRequested:
                    if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                    return
                except Exception as fast_err:
                    print(f"FastTelethon fallback for {message.id}: {fast_err}")

            if not file_path:
                try:
                    file_path = await message.download_media(
                        file=target_path,
                        progress_callback=internal_progress,
                    )
                except PauseRequested:
                    if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                    return
                except AttributeError as attr_err:
                    # Fallback for Telethon 1.38.x PhotoSize bug ('PhotoSize' object has no attribute 'location')
                    if "location" in str(attr_err) and getattr(message, 'photo', None):
                        try:
                            # Strategy 1: Download the photo object directly (higher level, often bypasses the bug)
                            file_path = await client.download_media(
                                message.photo,
                                file=target_path,
                                progress_callback=internal_progress
                            )
                        except Exception as e2:
                            print(f"Fallback Strategy 1 failed: {e2}")
                            # Strategy 2: Manual construction of InputPhotoFileLocation (lowest level)
                            from telethon.tl.types import InputPhotoFileLocation
                            photo = message.photo
                            best_size = None
                            if photo.sizes:
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
                                # If target_path is a directory, specify a filename
                                final_target = target_path
                                if os.path.isdir(final_target):
                                    final_target = os.path.join(final_target, file_name or f"Photo_{message.id}.jpg")
                                
                                try:
                                    file_path = await client.download_file(
                                        loc,
                                        file=final_target,
                                        progress_callback=internal_progress,
                                    )
                                except PauseRequested:
                                    if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                                    return
                                except Exception as e3:
                                    print(f"Fallback Strategy 2 failed: {e3}")
                                    # If both fail, we re-raise the original error to allow retry logic to take over
                                    raise attr_err
                            else:
                                print("Fallback Strategy 2 failed: No best_size found")
                                raise attr_err
                    else:
                        raise attr_err

            if complete_cb:
                complete_cb(message.id, filepath=file_path)
                
                # 📝 Message-Media Linker: Save sidecar .txt if message has text
                if file_path and os.path.exists(file_path):
                    # Clean up any leftover orphaned .part and .meta files for this completed file
                    part_f = file_path + ".part"
                    meta_f = part_f + ".meta"
                    if os.path.exists(part_f):
                        try: os.remove(part_f)
                        except Exception: pass
                    if os.path.exists(meta_f):
                        try: os.remove(meta_f)
                        except Exception: pass

                    if use_message_date and getattr(message, 'date', None):
                        try:
                            mtime = message.date.timestamp()
                            os.utime(file_path, (mtime, mtime))
                        except Exception as e:
                            print(f"Error setting file time for {file_path}: {e}")
                            
                    msg_text = (message.message or "").strip()
                    if msg_text:
                        base_path = os.path.splitext(file_path)[0]
                        txt_path = base_path + ".txt"
                        try:
                            with open(txt_path, "w", encoding="utf-8") as f:
                                f.write(msg_text)
                            if use_message_date and getattr(message, 'date', None):
                                os.utime(txt_path, (mtime, mtime))
                        except Exception as e:
                            print(f"Error saving sidecar text: {e}")
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
                if complete_cb: complete_cb(message.id, paused=False, error=True)

async def download_in_batches_headless(client, channel, messages, folder_name, batch_size, downloaded_state, progress_cb, complete_cb, task_cancel_event=None, max_speed_kb=None, msg_folder_resolver=None):
    semaphore = asyncio.Semaphore(batch_size)
    reserved_paths = set()
    
    def internal_complete(msg_id, paused=False, filepath=None, error=False):
        if not paused and not error and filepath:
            # Persistent state in SQLite - only mark completed if file was actually downloaded
            from telethon.utils import get_peer_id
            from database import mark_media_completed, update_media_downloaded_path
            try:
                ch_id = get_peer_id(channel)
                mark_media_completed(ch_id, msg_id)
                update_media_downloaded_path(ch_id, msg_id, filepath)
            except: pass
            downloaded_state.add(msg_id)
        if complete_cb:
            complete_cb(msg_id, paused=paused, filepath=filepath, error=error)

    async def download_message(message):
        async with semaphore:
            if task_cancel_event and task_cancel_event.is_set():
                if complete_cb: complete_cb(message.id, paused=True, filepath=None)
                return
            target_folder = msg_folder_resolver(message) if msg_folder_resolver else folder_name
            await download_single_file(client, channel, message, target_folder, progress_cb, internal_complete, task_cancel_event, max_speed_kb, reserved_paths=reserved_paths)

    tasks = [download_message(m) for m in messages if m.id not in downloaded_state]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def get_messages_by_type(client, channel, media_choice, min_id=None, max_id=None, limit=None, topic_id=None):
    """
    media_choice: 
    1 - Images
    2 - Videos
    3 - Files & Documents
    4 - ZIP files
    5 - Audio files
    6 - All Media
    """
    filter_type = None
    if media_choice == 1:
        filter_type = InputMessagesFilterPhotos()
    elif media_choice == 2:
        filter_type = InputMessagesFilterVideo()
    elif media_choice in [3, 4]:
        filter_type = InputMessagesFilterDocument()
    elif media_choice == 5:
        filter_type = InputMessagesFilterMusic()
    else:
        filter_type = None # All media
        
    kwargs = {"limit": limit}
    if min_id: kwargs["min_id"] = min_id
    if max_id: kwargs["max_id"] = max_id
    if topic_id: kwargs["reply_to"] = topic_id

    # Handle Audio / Voice combined fetch
    if media_choice == 5:
        try:
            music_msgs = await client.get_messages(channel, filter=InputMessagesFilterMusic(), **kwargs)
        except Exception:
            music_msgs = []
        try:
            voice_msgs = await client.get_messages(channel, filter=InputMessagesFilterVoice(), **kwargs)
        except Exception:
            voice_msgs = []
        try:
            doc_msgs = await client.get_messages(channel, filter=InputMessagesFilterDocument(), **kwargs)
            audio_docs = [m for m in doc_msgs if getattr(m, 'document', None) and getattr(m.document, 'mime_type', '').startswith("audio/")]
        except Exception:
            audio_docs = []
            
        combined_dict = {m.id: m for m in (list(music_msgs) + list(voice_msgs) + list(audio_docs))}
        return sorted(combined_dict.values(), key=lambda x: x.id, reverse=True)

    if filter_type:
        kwargs["filter"] = filter_type

    messages = await client.get_messages(channel, **kwargs)
    
    # Post-filtering
    if media_choice == 3:
        # Keep all valid documents
        messages = [m for m in messages if getattr(m, 'document', None) is not None]
    elif media_choice == 4:
        # ZIPs and compressed archives
        messages = [m for m in messages if getattr(m, 'document', None) and getattr(m.document, 'mime_type', '') in [
            "application/zip", "application/x-rar-compressed", "application/x-7z-compressed",
            "application/x-tar", "application/gzip", "application/x-bzip2"
        ]]
    elif media_choice == 6:
        # Only messages that actually contain media (photos, videos, docs, audios) - exclude plain text
        messages = [m for m in messages if getattr(m, 'media', None) is not None]
        
    return messages

async def fetch_categorized_media(client, channel, limit=None, topic_id=None):
    """
    Fetches up to `limit` messages for each distinct media category IN PARALLEL.
    Now uses a semaphore to prevent "Server closed the connection" errors and includes retries.
    """
    if limit is None:
        try:
            limit = int(os.getenv('FETCH_LIMIT', 2000))
        except:
            limit = 2000
            
    if topic_id:
        print(f"DEBUG: fetch_categorized_media using topic_id={topic_id}")
    # 🛡️ Limit concurrency to 1 simultaneous request to prevent Telegram from forcefully dropping connections
    sem = asyncio.Semaphore(1)
    
    async def get_messages_with_sem(filter_type=None, limit_val=limit):
        async with sem:
            for attempt in range(3):
                try:
                    kwargs = {}
                    if filter_type: kwargs['filter'] = filter_type
                    if topic_id is not None: kwargs['reply_to'] = topic_id
                    return await client.get_messages(channel, limit=limit_val, **kwargs)
                except Exception as e:
                    if "closed the connection" in str(e).lower() and attempt < 2:
                        await asyncio.sleep(1) # Wait a bit before retry
                        continue
                    raise e

    try:
        # Fetch fresh data from Telegram
        (photos, videos, round_vids, docs, music, voice, links, gifs, all_msgs, topic_ref) = await asyncio.gather(
            get_messages_with_sem(InputMessagesFilterPhotos()),
            get_messages_with_sem(InputMessagesFilterVideo()),
            get_messages_with_sem(InputMessagesFilterRoundVideo()),
            get_messages_with_sem(InputMessagesFilterDocument()),
            get_messages_with_sem(InputMessagesFilterMusic()),
            get_messages_with_sem(InputMessagesFilterVoice()),
            get_messages_with_sem(InputMessagesFilterUrl()),
            get_messages_with_sem(InputMessagesFilterGif()),
            get_messages_with_sem(limit_val=limit), # Base feed
            get_messages_with_sem(limit_val=1) # Reference message for topic title if possible
        )
        
        # If we have a topic_id, try to get the topic title from the first message
        topic_title = None
        if topic_id and all_msgs:
            # In Telethon, forum topics are technically replies.
            # We can try to fetch the service message that created the topic or just use one message.
            pass

        # 🗄️ CACHE RESULTS IN SQLite for faster tab switching
        from telethon.utils import get_peer_id
        try:
            ch_id = get_peer_id(channel)
            m_dict = {
                "Media": sorted(list(photos) + list(videos) + list(round_vids), key=lambda m: m.id, reverse=True),
                "Files": list(docs),
                "ZIPs": [m for m in docs if m.document and m.document.mime_type in ["application/zip", "application/x-rar-compressed", "application/x-7z-compressed"]],
                "Music": list(music),
                "Voice": list(voice),
                "Links": list(links),
                "GIFs": list(gifs),
                "Chat": [m for m in all_msgs if getattr(m, 'media', None) is None and (m.message or "").strip()]
            }
            cache_media_list(ch_id, m_dict)
        except Exception as cache_err:
            print(f"Failed to cache media: {cache_err}")
            
    except Exception as e:
        print(f"Fetch Categorized Media global failure: {e}")
        return {k.lower(): [] for k in ["Media", "Files", "ZIPs", "Music", "Voice", "Links", "GIFs", "Chat", "All"]}

    # ZIPs/Archives secondary filter from documents
    zips = [m for m in docs if m.document and m.document.mime_type in ["application/zip", "application/x-rar-compressed", "application/x-7z-compressed"]]
    
    # "Chat" = messages with NO media at all
    chats = [m for m in all_msgs if getattr(m, 'media', None) is None and (m.message or "").strip()]

    # Aggregate into "All" - Using a dict to deduplicate by message ID
    all_dict = {}
    all_raw = list(photos) + list(videos) + list(round_vids) + list(docs) + list(music) + list(voice) + list(links) + list(gifs) + list(chats)
    for m in all_raw:
        all_dict[m.id] = m
    all_sorted = sorted(all_dict.values(), key=lambda x: x.id, reverse=True)

    return {
        "All":   all_sorted[:limit], # Limit the "All" tab to the most recent items
        "Media": sorted(list(photos) + list(videos) + list(round_vids), key=lambda m: m.id, reverse=True)[:limit],
        "Files": list(docs),
        "ZIPs":  list(zips),
        "Music": list(music),
        "Voice": list(voice),
        "Links": list(links),
        "GIFs":  list(gifs),
        "Chat":  list(chats),
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
