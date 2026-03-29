import asyncio
import os
import threading
from PySide6.QtCore import QThread, Signal, QObject

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from core_downloader import (
    load_download_state,
    fetch_channel,
    get_messages_by_type,
    download_in_batches_headless,
    load_active_tasks,
    save_active_tasks
)

class WorkerSignals(QObject):
    # Auth Signals
    auth_needed = Signal()          # Needs phone
    code_needed = Signal(str)       # Needs code for phone
    password_needed = Signal()      # Needs 2FA password
    auth_success = Signal()
    auth_error = Signal(str)
    
    # Download Signals
    media_list_fetched = Signal(str, object, object) # channel_input, channel_obj, messages_dict
    channel_fetched = Signal(object, int) # channel, total_messages
    download_progress = Signal(str, int, int) # task_id, current_items, total_items
    file_progress = Signal(str, int, int, int, str) # task_id, msg_id, current_bytes, total_bytes, speed_str
    file_completed = Signal(str, int) # task_id, msg_id
    download_completed = Signal(str, str) # task_id, folder_name
    error_occurred = Signal(str, str) # task_id, error_msg


class TelegramWorker(QThread):
    def __init__(self, session_name, api_id, api_hash):
        super().__init__()
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.signals = WorkerSignals()
        self.loop = None
        self.client = None
        self.downloaded_state = load_download_state()
        
        self.task_cancel_events = {}

    def run(self):
        """Thread entry point. Starts the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash, loop=self.loop)
            self.loop.run_until_complete(self.check_auth())
        except ValueError:
            # API ID / Hash missing or invalid
            self.signals.auth_needed.emit()
        
        # Run forever processing asyncio tasks
        self.loop.run_forever()

    def set_credentials(self, api_id, api_hash):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        
        async def _reinit():
            if self.client:
                await self.client.disconnect()
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash, loop=self.loop)
            await self.check_auth()
            
        if self.loop:
            asyncio.run_coroutine_threadsafe(_reinit(), self.loop)

    def logout(self):
        async def _do_logout():
            if self.client:
                await self.client.log_out()
        if self.loop:
            asyncio.run_coroutine_threadsafe(_do_logout(), self.loop)

    def stop(self):
        if self.loop:
            for event in self.task_cancel_events.values():
                event.set()
            
            async def _cleanup():
                # Cleanly cancel any pending fetching or downloading tasks BEFORE disconnecting
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                if self.client:
                    await self.client.disconnect()
                    
            future = asyncio.run_coroutine_threadsafe(_cleanup(), self.loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
            
            self.loop.call_soon_threadsafe(self.loop.stop)

    # -------------------------------------------------------------------------
    # AUTHENTICATION
    # -------------------------------------------------------------------------
    async def check_auth(self):
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                self.signals.auth_needed.emit()
            else:
                self.signals.auth_success.emit()
        except Exception as e:
            self.signals.auth_error.emit(str(e))
            
    def start_login(self, api_id, api_hash, phone):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.current_phone = phone
        
        async def _req():
            try:
                if self.client:
                    await self.client.disconnect()
                
                self.client = TelegramClient(self.session_name, self.api_id, self.api_hash, loop=self.loop)
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    await self.client.send_code_request(phone)
                    self.signals.code_needed.emit(phone)
                else:
                    self.signals.auth_success.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
                
        if self.loop:
            asyncio.run_coroutine_threadsafe(_req(), self.loop)

    def submit_code(self, code):
        async def _sub():
            try:
                from telethon.errors import SessionPasswordNeededError
                await self.client.sign_in(getattr(self, 'current_phone', ''), code)
                self.signals.auth_success.emit()
            except SessionPasswordNeededError:
                self.signals.password_needed.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
        asyncio.run_coroutine_threadsafe(_sub(), self.loop)

    def submit_password(self, password):
        async def _pwd():
            try:
                await self.client.sign_in(password=password)
                self.signals.auth_success.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
        asyncio.run_coroutine_threadsafe(_pwd(), self.loop)

    def logout_async(self):
        async def _logout():
            await self.client.log_out()
            self.signals.auth_needed.emit()
        asyncio.run_coroutine_threadsafe(_logout(), self.loop)

    # -------------------------------------------------------------------------
    # DOWNLOADS
    # -------------------------------------------------------------------------
    def fetch_media_list(self, channel_input):
        """Called from Main UI to just fetch and group the messages for the modal."""
        asyncio.run_coroutine_threadsafe(self._fetch_media_list_coro(channel_input), self.loop)

    async def _fetch_media_list_coro(self, channel_input):
        try:
            channel = await fetch_channel(self.client, channel_input)
            
            # Fetch all types for the modal
            # (In a real scenario, this might need pagination, but we follow the prototype's get_messages_by_type)
            msgs_media = await get_messages_by_type(self.client, channel, 6) # 6 is ALL, or we do specific logic. 
            # The previous gui.py did essentially this to group them:
            messages_dict = {"media": [], "files": [], "links": []}
            for msg in msgs_media:
                if getattr(msg, 'document', None):
                    if msg.document.mime_type.startswith('video/') or msg.document.mime_type.startswith('image/'):
                        messages_dict["media"].append(msg)
                    else:
                        messages_dict["files"].append(msg)
                elif getattr(msg, 'photo', None):
                    messages_dict["media"].append(msg)
                # Links logic can be refined, just basic separation for now.
                
            self.signals.media_list_fetched.emit(channel_input, channel, messages_dict)
        except Exception as e:
            self.signals.error_occurred.emit(channel_input, f"Fetch Error: {str(e)}")

    def start_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None):
        """Called from Main UI Thread. Schedules download in asyncio loop."""
        tasks = load_active_tasks()
        found = False
        for t in tasks:
            if str(t.get("channel_input")) == str(channel_input) and t.get("media_id") == media_id:
                t["paused"] = is_paused
                t["download_path"] = download_path
                t["download_limit"] = download_limit
                t["max_speed_kb"] = max_speed_kb
                # Only overwrite selected_message_ids if it's explicitly provided
                if selected_message_ids is not None:
                    t["selected_message_ids"] = selected_message_ids
                found = True
                break
        if not found:
            tasks.append({
                "channel_input": channel_input,
                "media_id": media_id,
                "paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "selected_message_ids": selected_message_ids
            })
        save_active_tasks(tasks)

        asyncio.run_coroutine_threadsafe(
            self._download_coro(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids), 
            self.loop
        )

    def pause_download(self, task_id):
        if task_id in self.task_cancel_events:
            self.task_cancel_events[task_id].set()
            
        try:
            channel_input, media_id_str = task_id.rsplit('_', 1)
            media_id = int(media_id_str)
            tasks = load_active_tasks()
            for t in tasks:
                if str(t.get("channel_input")) == channel_input and t.get("media_id") == media_id:
                    t["paused"] = True
                    break
            save_active_tasks(tasks)
        except Exception:
            pass

    def resume_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb):
        # Pass None so it finds remaining
        self.start_download(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None)
        
    def cancel_download(self, task_id):
        self.pause_download(task_id)
        if task_id in self.task_cancel_events:
            del self.task_cancel_events[task_id]
            
        try:
            channel_input, media_id_str = task_id.rsplit('_', 1)
            media_id = int(media_id_str)
            tasks = load_active_tasks()
            tasks = [t for t in tasks if not (str(t.get("channel_input")) == channel_input and t.get("media_id") == media_id)]
            save_active_tasks(tasks)
        except Exception:
            pass

    async def _download_coro(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids):
        try:
            channel = await fetch_channel(self.client, channel_input)
            task_id = f"{channel_input}_{media_id}"
            title = channel.title or f"Channel ID: {channel.id}"
            
            # 1. Clean up potential duplicates in active_tasks.json now that we know the true channel ID
            try:
                tasks = load_active_tasks()
                deduped_tasks = []
                seen_channel_ids = set()
                
                # We want to keep the current task and remove any others that resolve to the same numeric channel ID
                # To be safe, we'll only deduplicate if the media_id matches too.
                for tk in tasks:
                    match = False
                    # Check if this task in the list matches our current resolved channel
                    if tk.get("media_id") == media_id:
                        # If it's the exact same input, it's definitely a duplicate
                        if str(tk.get("channel_input")) == str(channel_input):
                            match = True
                        # If it's a numeric ID that matches our resolved ID
                        elif str(tk.get("channel_input")).replace("-100", "") == str(channel.id).replace("-100", ""):
                            match = True
                    
                    if match:
                        if task_id not in seen_channel_ids:
                            seen_channel_ids.add(task_id)
                            deduped_tasks.append(tk)
                    else:
                        deduped_tasks.append(tk)
                save_active_tasks(deduped_tasks)
            except Exception as e:
                print(f"Deduplication error: {e}")
                
            # 2. Emit placeholder so the card appears instantly
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": f"⏳ Loading... ({title})",
                "total_items": 0,
                "completed": 0,
                "folder_name": download_path,
                "channel_input": channel_input,
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": []
            }, 0)

            # 3. Fetch real messages (this takes time)
            messages = await get_messages_by_type(self.client, channel, media_id)
            
            # Filter if specific messages were selected
            if selected_message_ids is not None:
                messages = [m for m in messages if m.id in selected_message_ids]
            
            all_messages_count = len(messages)
            messages_to_download = [m for m in messages if m.id not in self.downloaded_state]
            total_items = all_messages_count
            completed_initial = all_messages_count - len(messages_to_download)
            
            base_folder = {1: "images", 2: "videos", 3: "pdfs", 4: "zips", 5: "audio", 6: "all_media"}
            folder_name = os.path.join(download_path, channel.title or str(channel.id), base_folder.get(media_id, "all_media"))
            os.makedirs(folder_name, exist_ok=True)
            
            task_id = f"{channel.id}_{media_id}"
            title = channel.title or f"Channel ID: {channel.id}"
            
            # Collect file metadata for the UI list
            files_metadata = []
            for msg in messages:
                fname = f"Message_{msg.id}"
                fsize = 0
                try:
                    if getattr(msg, 'document', None):
                        # Safe file name extraction
                        file_ext = ""
                        if hasattr(msg, 'file') and msg.file:
                            fname = msg.file.name or fname
                            file_ext = msg.file.ext or ""
                        
                        if fname == f"Message_{msg.id}":
                            fname = f"Document_{msg.id}{file_ext}"
                            
                        fsize = getattr(msg.document, 'size', 0)
                        
                    elif getattr(msg, 'photo', None):
                        fname = f"Photo_{msg.id}.jpg"
                        if hasattr(msg.photo, 'sizes') and msg.photo.sizes:
                            # Iterate backwards to find the largest size
                            for s in reversed(msg.photo.sizes):
                                if hasattr(s, 'size'):
                                    fsize = s.size
                                    break
                except Exception as e:
                    print(f"Warning: metadata extraction for {msg.id} failed: {e}")

                files_metadata.append({
                    "id": msg.id,
                    "name": fname,
                    "size": fsize,
                    "completed": msg.id in self.downloaded_state
                })

            global_cancel_event = asyncio.Event()
            global_cancel_event.clear()
            self.task_cancel_events[task_id] = global_cancel_event
            if is_paused:
                global_cancel_event.set()

            # 4. Emit the REAL metadata to update the placeholder card
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": title,
                "total_items": total_items,
                "completed": completed_initial,
                "folder_name": folder_name,
                "channel_input": channel_input,
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": files_metadata
            }, total_items)
            
            if not messages_to_download or is_paused:
                if not messages_to_download:
                    self.signals.download_completed.emit(task_id, folder_name)
                return

            completed_count = [completed_initial]

            def on_file_complete(msg_id, paused=False, filepath=None):
                if not paused:
                    self.signals.file_completed.emit(task_id, msg_id)
                    completed_count[0] += 1
                    self.signals.download_progress.emit(task_id, completed_count[0], total_items)
                    if completed_count[0] >= total_items:
                        # Remove from active tasks
                        try:
                            t_chan, t_media_str = task_id.rsplit('_', 1)
                            t_media = int(t_media_str)
                            tkList = load_active_tasks()
                            tkList = [tk for tk in tkList if not (str(tk.get("channel_input")) == t_chan and tk.get("media_id") == t_media)]
                            save_active_tasks(tkList)
                        except Exception:
                            pass
                        
                        self.signals.download_completed.emit(task_id, folder_name)

            def on_file_progress(msg_id, current, total, speed_str="0 KB/s"):
                self.signals.file_progress.emit(task_id, msg_id, current, total, speed_str)

            await download_in_batches_headless(
                messages=messages_to_download,
                folder_name=folder_name,
                batch_size=download_limit,
                downloaded_state=self.downloaded_state,
                progress_cb=on_file_progress,
                complete_cb=on_file_complete,
                task_cancel_event=global_cancel_event,
                max_speed_kb=max_speed_kb if max_speed_kb > 0 else None
            )

        except Exception as e:
            self.signals.error_occurred.emit(channel_input, str(e))
