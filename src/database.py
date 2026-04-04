import sqlite3
import os
import json
from resource_utils import get_project_root

DB_PATH = os.path.join(get_project_root(), "downloader.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Media Cache: Persistent storage for every message metadata we've seen
    # This replaces the need to re-fetch from Telegram for every tab switch
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media_cache (
        msg_id INTEGER,
        channel_id TEXT,
        media_type TEXT, 
        title TEXT,
        size INTEGER,
        date TEXT,
        completed INTEGER DEFAULT 0,
        raw_json TEXT, 
        PRIMARY KEY (msg_id, channel_id)
    )
    """)
    
    # 2. Tasks: The active download queue
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, -- 'channelId_mediaId'
        channel_input TEXT,
        media_id INTEGER,
        paused INTEGER DEFAULT 0,
        download_path TEXT,
        download_limit INTEGER,
        max_speed_kb INTEGER,
        selected_ids TEXT, -- JSON list of message IDs
        title TEXT,
        total_items INTEGER,
        folder_name TEXT
    )
    """)
    
    conn.commit()
    conn.close()

# --- TASK MANAGEMENT ---

def save_task_db(task):
    """Saves or updates a single task object in SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 🛡️ Deduplication normalized key
    ch = str(task.get("channel_input", "")).strip()
    ch_key = ch.replace("-100", "", 1) if ch.startswith("-100") else ch
    media_id = task.get("media_id", 6)
    task_id = f"{ch_key}_{media_id}"
    
    selected_json = json.dumps(task.get("selected_message_ids", []))
    
    cursor.execute("""
    INSERT INTO tasks (
        task_id, channel_input, media_id, paused, download_path, 
        download_limit, max_speed_kb, selected_ids, title, total_items, folder_name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(task_id) DO UPDATE SET
        channel_input=excluded.channel_input,
        paused=excluded.paused,
        download_path=excluded.download_path,
        download_limit=excluded.download_limit,
        max_speed_kb=excluded.max_speed_kb,
        selected_ids=excluded.selected_ids,
        title=excluded.title,
        total_items=excluded.total_items,
        folder_name=excluded.folder_name
    """, (
        task_id, ch, media_id, 1 if task.get("paused") else 0,
        task.get("download_path"), task.get("download_limit"),
        task.get("max_speed_kb"), selected_json, task.get("title"),
        task.get("total_items"), task.get("folder_name")
    ))
    
    conn.commit()
    conn.close()

def load_active_tasks_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks")
    rows = cursor.fetchall()
    
    tasks = []
    for r in rows:
        t = dict(r)
        t["paused"] = bool(t["paused"])
        t["selected_message_ids"] = json.loads(t["selected_ids"])
        tasks.append(t)
    
    conn.close()
    return tasks

def get_task_db(ch_input, media_id=6):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    ch_key = str(ch_input).replace("-100", "", 1)
    task_id = f"{ch_key}_{media_id}"
    cursor.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        t = dict(row)
        t["selected_message_ids"] = json.loads(t["selected_ids"])
        return t
    return None

def remove_task_db(ch_input, media_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ch_key = str(ch_input).replace("-100", "", 1)
    task_id = f"{ch_key}_{media_id}"
    cursor.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
    conn.commit()
    conn.close()

# --- MEDIA CACHE ---

def cache_media_list(channel_id, messages_dict):
    """
    Saves a full categorized dictionary from fetch_categorized_media into DB.
    messages_dict: { 'Media': [msg_objs], 'Files': [msg_objs], ... }
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Normalize channel ID
    c_id = str(channel_id).replace("-100", "", 1)
    
    # We use a batch transaction for speed
    for category, msgs in messages_dict.items():
        for m in msgs:
            # We don't save raw telethon objects, just the essentials
            m_title = "Unknown File"
            m_size = 0
            if hasattr(m, 'file') and m.file:
                m_title = m.file.name or f"File_{m.id}{m.file.ext}"
                m_size = m.file.size
            elif hasattr(m, 'photo') and m.photo:
                m_title = f"Photo_{m.id}.jpg"
                # Find size from photo.sizes
                if hasattr(m.photo, 'sizes'):
                    m_size = m.photo.sizes[-1].size if hasattr(m.photo.sizes[-1], 'size') else 0

            cursor.execute("""
            INSERT INTO media_cache (msg_id, channel_id, media_type, title, size, date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(msg_id, channel_id) DO UPDATE SET
                media_type=excluded.media_type,
                title=excluded.title,
                size=excluded.size
            """, (m.id, c_id, category, m_title, m_size, str(m.date) if hasattr(m, 'date') else ""))
            
    conn.commit()
    conn.close()

def get_cached_media(channel_id, category=None):
    """Retrieves cached media for a channel from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    c_id = str(channel_id).replace("-100", "", 1)
    if category:
        cursor.execute("SELECT * FROM media_cache WHERE channel_id=? AND media_type=? ORDER BY msg_id DESC", (c_id, category))
    else:
        cursor.execute("SELECT * FROM media_cache WHERE channel_id=? ORDER BY msg_id DESC", (c_id,))
        
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def mark_media_completed(channel_id, msg_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    c_id = str(channel_id).replace("-100", "", 1)
    cursor.execute("UPDATE media_cache SET completed=1 WHERE msg_id=? AND channel_id=?", (msg_id, c_id))
    conn.commit()
    conn.close()

def get_completed_state_db():
    """Returns a set of (channel_id, msg_id) for fast lookup of finished files."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, msg_id FROM media_cache WHERE completed=1")
    res = set(cursor.fetchall())
    conn.close()
    return res

def migrate_json_to_db():
    from resource_utils import get_project_root
    tasks_file = os.path.join(get_project_root(), "active_tasks.json")
    state_file = os.path.join(get_project_root(), "download_state.json")
    import json
    
    if not os.path.exists(tasks_file) and not os.path.exists(state_file):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Migrate tasks
    if os.path.exists(tasks_file):
        try:
            with open(tasks_file, "r") as f:
                tasks = json.load(f)
                for t in tasks:
                    ch = str(t.get("channel_input", ""))
                    ch_key = ch.replace("-100", "", 1) if ch.startswith("-100") else ch
                    tid = f"{ch_key}_{t.get('media_id', 6)}"
                    cursor.execute("""
                    INSERT OR IGNORE INTO tasks (task_id, channel_input, media_id, paused, download_path, download_limit, max_speed_kb, selected_ids, title, total_items, folder_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (tid, ch, t.get('media_id', 6), 1 if t.get('paused') else 0, t.get('download_path'), t.get('download_limit'), t.get('max_speed_kb'), json.dumps(t.get('selected_message_ids', [])), t.get('title'), t.get('total_items'), t.get('folder_name')))
            os.rename(tasks_file, tasks_file + ".bak")
        except: pass
        
    # Migrate download state
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                for mid in state:
                    cursor.execute("INSERT OR IGNORE INTO media_cache (msg_id, channel_id, completed) VALUES (?, ?, ?)", (mid, "legacy", 1))
            os.rename(state_file, state_file + ".bak")
        except: pass
        
    conn.commit()
    conn.close()
