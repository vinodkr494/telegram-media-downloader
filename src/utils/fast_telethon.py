import math
import os
import json
import asyncio
import time
from telethon.tl.functions.upload import GetFileRequest
from telethon.utils import get_input_location

CHUNK_SIZE = 512 * 1024  # 512 KB per chunk (Telegram MTProto max limit)


def _load_meta(meta_path, file_size, total_parts):
    """Safely loads download progress metadata if it exists and is valid."""
    if not os.path.exists(meta_path):
        return set()
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("file_size") == file_size and data.get("total_parts") == total_parts:
                return set(data.get("completed_parts", []))
    except Exception:
        pass
    return set()


def _save_meta(meta_path, file_size, chunk_size, total_parts, completed_parts):
    """Safely writes download progress metadata using atomic rename."""
    try:
        temp_meta = meta_path + ".tmp"
        data = {
            "file_size": file_size,
            "chunk_size": chunk_size,
            "total_parts": total_parts,
            "completed_parts": list(completed_parts)
        }
        with open(temp_meta, "w", encoding="utf-8") as f:
            json.dump(data, f)
        if os.path.exists(temp_meta):
            os.replace(temp_meta, meta_path)
    except Exception:
        pass


def _atomic_finalize_sync(temp_path, target_path, meta_path=None):
    """Atomically renames temp_path to target_path with retries for Windows file locks."""
    for attempt in range(5):
        try:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            os.replace(temp_path, target_path)
            # Remove meta_path only after temp_path is successfully renamed to target_path
            if meta_path and os.path.exists(meta_path):
                try:
                    os.remove(meta_path)
                except Exception:
                    pass
            return True
        except (PermissionError, OSError) as e:
            if attempt < 4:
                time.sleep(0.3)
            else:
                raise e
    return False


async def _atomic_finalize_async(temp_path, target_path, meta_path=None):
    """Async atomic rename with retries for Windows file locks."""
    for attempt in range(5):
        try:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            os.replace(temp_path, target_path)
            # Remove meta_path only after temp_path is successfully renamed to target_path
            if meta_path and os.path.exists(meta_path):
                try:
                    os.remove(meta_path)
                except Exception:
                    pass
            return True
        except (PermissionError, OSError) as e:
            if attempt < 4:
                await asyncio.sleep(0.3)
            else:
                raise e
    return False


async def _download_part(client, location, offset, limit, dc_id=None):
    """Fetches a single chunk from Telegram with timeout and retries."""
    for attempt in range(5):
        try:
            req = GetFileRequest(location=location, offset=offset, limit=limit)
            if dc_id:
                sender = await asyncio.wait_for(client._borrow_exported_sender(dc_id), timeout=15.0)
                try:
                    result = await asyncio.wait_for(sender.send(req), timeout=25.0)
                finally:
                    await client._return_exported_sender(sender)
            else:
                result = await asyncio.wait_for(client(req), timeout=25.0)
            return result.bytes if result else b""
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if attempt < 4:
                from telethon.errors import FloodWaitError
                if isinstance(e, FloodWaitError):
                    wait = getattr(e, 'seconds', 1.0)
                    await asyncio.sleep(wait)
                else:
                    wait = getattr(e, 'seconds', 1.0)
                    await asyncio.sleep(min(wait, 3.0))
            else:
                raise e


async def fast_download_file(client, location, target_path, file_size, dc_id=None, progress_callback=None, cancel_event=None, workers=4):
    """
    Downloads media at maximum throughput using parallel chunk streams with resumable state.
    Falls back gracefully if parallel streaming is not supported for the media.
    """
    if file_size <= 0:
        return False

    # If target file is already fully downloaded on disk, skip and succeed
    if os.path.exists(target_path) and os.path.getsize(target_path) >= file_size:
        return True

    total_parts = math.ceil(file_size / CHUNK_SIZE)
    if total_parts <= 1 or workers <= 1:
        # Small file: single chunk is fast enough directly
        return False

    # Extract dc_id and InputFileLocation TLObject
    if isinstance(location, tuple) and len(location) == 2:
        dc_id, location = location
    elif not hasattr(location, 'SUBCLASS_OF_ID') or location.SUBCLASS_OF_ID != 0x1523d462:
        try:
            dc_id, location = get_input_location(location)
        except Exception:
            return False

    if not location or not hasattr(location, 'SUBCLASS_OF_ID'):
        return False

    temp_path = target_path + ".part"
    meta_path = temp_path + ".meta"
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    # Check existing .part and .meta files for resumption
    completed_parts = set()
    if os.path.exists(temp_path):
        existing_part_size = os.path.getsize(temp_path)
        if existing_part_size == file_size:
            completed_parts = _load_meta(meta_path, file_size, total_parts)
            # Only finalize if metadata confirms all parts are genuinely completed
            if total_parts > 0 and len(completed_parts) == total_parts:
                await _atomic_finalize_async(temp_path, target_path, meta_path)
                return True
        else:
            # File size mismatch, re-truncate
            with open(temp_path, "wb") as f:
                f.truncate(file_size)
            completed_parts = set()
            _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)
    else:
        with open(temp_path, "wb") as f:
            f.truncate(file_size)
        completed_parts = set()
        _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)

    missing_parts = [idx for idx in range(total_parts) if idx not in completed_parts]
    if not missing_parts and total_parts > 0:
        await _atomic_finalize_async(temp_path, target_path, meta_path)
        return True

    queue = asyncio.Queue()
    for idx in missing_parts:
        queue.put_nowait(idx)

    # Calculate initial downloaded bytes from already completed parts
    init_bytes = 0
    for idx in completed_parts:
        if idx == total_parts - 1:
            init_bytes += file_size - (idx * CHUNK_SIZE)
        else:
            init_bytes += CHUNK_SIZE

    downloaded_bytes = [init_bytes]
    lock = asyncio.Lock()
    file_handle = open(temp_path, "r+b")

    # Initial progress notification if resumed with existing parts
    if init_bytes > 0 and progress_callback:
        try:
            res = progress_callback(init_bytes, file_size)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass

    class DownloadCancelled(Exception): pass

    save_meta_counter = [0]

    async def worker():
        while not queue.empty():
            if cancel_event and cancel_event.is_set():
                raise DownloadCancelled()

            try:
                part_idx = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            offset = part_idx * CHUNK_SIZE
            limit = CHUNK_SIZE

            chunk = await _download_part(client, location, offset, limit, dc_id=dc_id)
            if not chunk:
                queue.task_done()
                continue

            # If last chunk returned extra padding past file_size, trim it
            if offset + len(chunk) > file_size:
                chunk = chunk[:file_size - offset]

            async with lock:
                file_handle.seek(offset)
                file_handle.write(chunk)
                downloaded_bytes[0] += len(chunk)
                completed_parts.add(part_idx)
                current = downloaded_bytes[0]

                save_meta_counter[0] += 1
                if save_meta_counter[0] % 4 == 0 or len(completed_parts) == total_parts:
                    _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)

            if progress_callback:
                res = progress_callback(current, file_size)
                if asyncio.iscoroutine(res):
                    await res

            queue.task_done()

    tasks = []
    try:
        tasks = [asyncio.create_task(worker()) for _ in range(min(workers, len(missing_parts)))]
        await asyncio.gather(*tasks)
    except DownloadCancelled:
        # User paused/cancelled: persist current meta for future resume
        _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)
        return False
    except Exception as e:
        _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)
        raise e
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            file_handle.flush()
        except Exception:
            pass
        try:
            file_handle.close()
        except Exception:
            pass

    if cancel_event and cancel_event.is_set():
        _save_meta(meta_path, file_size, CHUNK_SIZE, total_parts, completed_parts)
        return False

    if len(completed_parts) == total_parts or downloaded_bytes[0] >= file_size:
        await _atomic_finalize_async(temp_path, target_path, meta_path)
        return True

    return False
