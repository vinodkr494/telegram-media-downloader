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
from resource_utils import get_project_root

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
    def __init__(self, session_name, api_id, api_hash, parent=None):
        super().__init__(parent)
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.signals = WorkerSignals()
        self.loop = None
        self.client = None
        self.task_cancel_events = {}
        self.running_tasks = {} # task_id -> future or task

    def run(self):
        """Thread entry point. Starts the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            session_full_path = os.path.join(get_project_root(), self.session_name)
            self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
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
            session_full_path = os.path.join(get_project_root(), self.session_name)
            self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
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
            print("DEBUG: check_auth started, connecting client...")
            await self.client.connect()
            print("DEBUG: check_auth: connected. checking authorization...")
            if not await self.client.is_user_authorized():
                print("DEBUG: check_auth: NOT authorized, emitting auth_needed")
                self.signals.auth_needed.emit()
            else:
                # Pre-fetch dialogs to populate entity cache (helps resolving numeric IDs)
                print("DEBUG: check_auth: authorized, pre-fetching dialogs...")
                await self.client.get_dialogs(limit=50)
                print("DEBUG: check_auth: pre-fetch done, emitting auth_success")
                self.signals.auth_success.emit()
        except Exception as e:
            print(f"DEBUG: check_auth error: {e}")
            self.signals.auth_error.emit(str(e))
            
    def start_login(self, api_id, api_hash, phone):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.current_phone = phone
        
        async def _req():
            try:
                if self.client:
                    await self.client.disconnect()
                
                session_full_path = os.path.join(get_project_root(), self.session_name)
                self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    await self.client.send_code_request(phone)
                    self.signals.code_needed.emit(phone)
                else:
                    await self.client.get_dialogs(limit=50)
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
                await self.client.get_dialogs(limit=50)
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
                await self.client.get_dialogs(limit=50)
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
            
            # Fetch all types for the modal using centralized logic
            from core_downloader import fetch_categorized_media
            messages_dict = await fetch_categorized_media(self.client, channel)
            
            # Normalize keys to lowercase for UI compatibility if needed, 
            # though we can just update UI to use these keys.
            # Convert keys to lowercase to match previous contract
            messages_dict = {k.lower(): v for k, v in messages_dict.items()}
            
            self.signals.media_list_fetched.emit(channel_input, channel, messages_dict)
        except Exception as e:
            self.signals.error_occurred.emit(channel_input, f"Fetch Error: {str(e)}")

    def start_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None, task_id=None):
        """Called from Main UI Thread. Schedules download in asyncio loop."""
        tasks = load_active_tasks()
        found = False
        found_task = None
        ch_clean = str(channel_input or "").replace("-100", "", 1)
        for t in tasks:
            if not isinstance(t, dict): continue
            # Match by explicit ID or by the same rule we use to generate task_id
            tk_chan = str(t.get("channel_input", "")).replace("-100", "", 1)
            tk_media = t.get("media_id")
            generated_id = f"{tk_chan}_{tk_media}"
            
            if task_id == generated_id or (task_id and t.get("task_id") == task_id):
                found_task = t
                break
            
            if not task_id and tk_chan == ch_clean and tk_media == media_id:
                found_task = t
                break
        
        if found_task:
            t = found_task
            t["paused"] = is_paused
            t["download_path"] = download_path
            t["download_limit"] = download_limit
            t["max_speed_kb"] = max_speed_kb
            # Only overwrite selected_message_ids if it's explicitly provided
            if selected_message_ids is not None:
                t["selected_message_ids"] = selected_message_ids
                t["total_items"] = len(selected_message_ids)
            else:
                selected_message_ids = t.get("selected_message_ids")
        if not bool(found_task):
            tasks.append({
                "channel_input": channel_input,
                "media_id": media_id,
                "paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "selected_message_ids": selected_message_ids,
                "title": f"Channel: {channel_input}", # Placeholder
                "total_items": len(selected_message_ids) if selected_message_ids else 0
            })
        save_active_tasks(tasks)

        # 🛡️ Prevent duplicate/competing loops for the same task
        # We start with the input-based ID as a temporary key
        actual_task_id = task_id or f"{ch_clean}_{media_id}"
        if actual_task_id in self.running_tasks:
            # We must be careful not to cancel the same task we JUST scheduled if this is called very rapidly,
            # but usually start_download is user-triggered.
            old_task = self.running_tasks[actual_task_id]
            if isinstance(old_task, asyncio.Task) and not old_task.done():
                old_task.cancel()
            elif hasattr(old_task, 'cancel'): # It might be a Future
                old_task.cancel()
                
        self.running_tasks[actual_task_id] = asyncio.run_coroutine_threadsafe(
            self._download_coro(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids, actual_task_id), 
            self.loop
        )

    def pause_download(self, task_id):
        if self.loop and task_id in self.task_cancel_events:
            event = self.task_cancel_events[task_id]
            self.loop.call_soon_threadsafe(event.set)
            
        try:
            channel_input, media_id_str = task_id.rsplit('_', 1)
            media_id = int(media_id_str)
            ch_clean = channel_input.replace("-100", "", 1)
            tasks = load_active_tasks()
            for t in tasks:
                tk_chan = str(t.get("channel_input")).replace("-100", "", 1)
                if tk_chan == ch_clean and t.get("media_id") == media_id:
                    t["paused"] = True
                    break
            save_active_tasks(tasks)
        except Exception:
            pass

    def resume_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb):
        # Explicitly pass is_paused=False to resume
        self.start_download(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None)
        
    def cancel_download(self, task_id):
        self.pause_download(task_id)
        if task_id in self.task_cancel_events:
            del self.task_cancel_events[task_id]
            
        try:
            channel_input, media_id_str = task_id.rsplit('_', 1)
            media_id = int(media_id_str)
            ch_clean = channel_input.replace("-100", "", 1)
            tasks = load_active_tasks()
            new_tasks = []
            for t in tasks:
                tk_chan = str(t.get("channel_input")).replace("-100", "", 1)
                if tk_chan == ch_clean and t.get("media_id") == media_id:
                    continue
                new_tasks.append(t)
            save_active_tasks(new_tasks)
        except Exception:
            pass

    async def _download_coro(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids, original_task_id=None):
        try:
            channel = await fetch_channel(self.client, channel_input)
            # Use the canonical numeric ID for task identification once resolved.
            # IN TELETHON: PeerChannel, PeerChat, and PeerUser have raw IDs. 
            # For channels, we must include the -100 prefix for stable global IDs.
            from telethon.utils import get_peer_id
            resolved_chan_id = str(get_peer_id(channel))
            task_id = f"{resolved_chan_id}_{media_id}"
            
            # 🛡️ ID HIJACK: If we were started with a username/title, switch the tracker to use the numeric ID
            if original_task_id and original_task_id != task_id:
                if original_task_id in self.running_tasks:
                    # Don't delete, just ensure we update the cancel event if it exists
                    if original_task_id in self.task_cancel_events:
                        self.task_cancel_events[task_id] = self.task_cancel_events.pop(original_task_id)
                
                # Check if another task with the REAL ID is already running
                if task_id in self.running_tasks and self.running_tasks[task_id] != asyncio.current_task():
                    old_t = self.running_tasks[task_id]
                    if not old_t.done():
                        old_t.cancel()
            
            self.running_tasks[task_id] = asyncio.current_task()
            
            # 0. Load the downloaded state (Isolated by channel ID)
            resolved_peer_id = None
            try:
                resolved_peer_id = get_peer_id(channel)
            except: pass
            downloaded_state = load_download_state(resolved_peer_id)

            title = channel.title or f"Channel ID: {channel.id}"
            
            # 1. Update active_tasks.json to use the numeric ID for future persistence
            try:
                tasks = load_active_tasks()
                updated_tasks = []
                found_and_updated = False
                
                ch_resolved_clean = resolved_chan_id.replace("-100", "", 1) if resolved_chan_id.startswith("-100") else resolved_chan_id
                for tk in tasks:
                    match = False
                    tk_chan_raw = str(tk.get("channel_input"))
                    tk_chan_clean = tk_chan_raw.replace("-100", "", 1) if tk_chan_raw.startswith("-100") else tk_chan_raw
                    # If this is the task we just resolved (either by input string or numeric ID)
                    if tk.get("media_id") == media_id:
                        # Match either by exact string OR by clean ID equivalence
                        if tk_chan_raw == str(channel_input) or tk_chan_clean == ch_resolved_clean:
                            match = True
                    
                    if match and not found_and_updated:
                        tk["channel_input"] = resolved_chan_id
                        tk["title"] = title # PERSIST TITLE
                        updated_tasks.append(tk)
                        found_and_updated = True
                    else:
                        updated_tasks.append(tk)
                
                # If for some reason it wasn't in the list, add it now (integrity check)
                if not found_and_updated:
                    updated_tasks.append({
                        "channel_input": resolved_chan_id,
                        "media_id": media_id,
                        "paused": is_paused,
                        "download_path": download_path,
                        "download_limit": download_limit,
                        "max_speed_kb": max_speed_kb,
                        "selected_message_ids": selected_message_ids
                    })
                save_active_tasks(updated_tasks)
            except Exception as e:
                print(f"Persistence update error: {e}")
                
            # 2. Emit placeholder so the card appears (using the stable numeric task_id)
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": f"⏳ Loading... ({title})",
                "total_items": 0,
                "completed": 0,
                "folder_name": download_path,
                "channel_input": resolved_chan_id,
                "original_input": channel_input, # CRITICAL: Tell UI where we came from
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
            messages_to_download = [m for m in messages if m.id not in downloaded_state]
            total_items = all_messages_count
            completed_initial = all_messages_count - len(messages_to_download)
            
            base_folder_map = {1: "images", 2: "videos", 3: "pdfs", 4: "zips", 5: "audio", 6: "all_media"}
            category_name = base_folder_map.get(media_id, "all_media")
            
            # 📂 Dynamic Path Templating
            # Supported: {channel}, {category}, {year}, {month}, {day}
            from datetime import datetime
            now_dt = datetime.now()
            
            template = download_path
            # If the user just gave a plain path, we append the channel/category as default
            if "{" not in template:
                template = os.path.join(template, "{channel}", "{category}")
            
            safe_title = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in (channel.title or str(channel.id))])
            
            folder_name = template.format(
                channel=safe_title,
                category=category_name,
                year=now_dt.strftime("%Y"),
                month=now_dt.strftime("%m"),
                day=now_dt.strftime("%d")
            )
            
            os.makedirs(folder_name, exist_ok=True)
            
            # Ensure folder_name is absolute or correctly rooted
            if not os.path.isabs(folder_name):
                folder_name = os.path.abspath(folder_name)

            # 4. Emit the REAL metadata to update the placeholder card
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": title,
                "total_items": total_items,
                "completed": completed_initial,
                "folder_name": folder_name,
                "channel_input": resolved_chan_id,
                "original_input": channel_input, # Maintain origin trace!
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": [] # Will populate in Card's refresh_from_metadata
            }, total_items)
            
            # 5. Update persistence with resolved metadata
            try:
                tasks = load_active_tasks()
                for tk in tasks:
                    tk_chan_clean = str(tk.get("channel_input")).replace("-100", "", 1)
                    if tk_chan_clean == resolved_chan_id.replace("-100", "", 1) and tk.get("media_id") == media_id:
                        tk["title"] = title
                        tk["total_items"] = total_items
                        tk["folder_name"] = folder_name
                        break
                save_active_tasks(tasks)
            except Exception: pass
            
            # Build actual files_metadata for current messages
            files_metadata = []
            for msg in messages:
                fname = f"Message_{msg.id}"
                fsize = 0
                try:
                    if getattr(msg, 'document', None):
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
                            for s in reversed(msg.photo.sizes):
                                if hasattr(s, 'size'):
                                    fsize = s.size
                                    break
                except Exception: pass

                files_metadata.append({
                    "id": msg.id,
                    "name": fname,
                    "size": fsize,
                    "completed": msg.id in downloaded_state
                })

            # Update the same card again with full file list
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": title,
                "total_items": total_items,
                "completed": completed_initial,
                "folder_name": folder_name,
                "channel_input": resolved_chan_id,
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": files_metadata
            }, total_items)
            
            if task_id in self.task_cancel_events:
                global_cancel_event = self.task_cancel_events[task_id]
            else:
                global_cancel_event = asyncio.Event()
                self.task_cancel_events[task_id] = global_cancel_event
            
            global_cancel_event.clear()
            
            if is_paused:
                global_cancel_event.set()
                return

            # Mark as running
            self.running_tasks[task_id] = asyncio.current_task()

            if not messages_to_download:
                self.signals.download_completed.emit(task_id, folder_name)
                if task_id in self.running_tasks: del self.running_tasks[task_id]
                return

            completed_count = [completed_initial]

            def on_file_complete(msg_id, paused=False, filepath=None):
                if not paused:
                    self.signals.file_completed.emit(task_id, msg_id)
                    completed_count[0] += 1
                    self.signals.download_progress.emit(task_id, completed_count[0], total_items)
                    if completed_count[0] >= total_items:
                        # Remove from active tasks using the stable numeric ID
                        try:
                            tkList = load_active_tasks()
                            tkList = [tk for tk in tkList if not (str(tk.get("channel_input")) == resolved_chan_id and tk.get("media_id") == media_id)]
                            save_active_tasks(tkList)
                        except Exception as e:
                            print(f"Error removing task: {e}")
                        
                        self.signals.download_completed.emit(task_id, folder_name)

            def on_file_progress(msg_id, current, total, speed_str="0 KB/s"):
                self.signals.file_progress.emit(task_id, msg_id, current, total, speed_str)

            await download_in_batches_headless(
                client=self.client,
                channel=channel,
                messages=messages_to_download,
                folder_name=folder_name,
                batch_size=download_limit,
                downloaded_state=downloaded_state,
                progress_cb=on_file_progress,
                complete_cb=on_file_complete,
                task_cancel_event=global_cancel_event,
                max_speed_kb=max_speed_kb if max_speed_kb > 0 else None
            )
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

        except Exception as e:
            self.signals.error_occurred.emit(channel_input, str(e))
