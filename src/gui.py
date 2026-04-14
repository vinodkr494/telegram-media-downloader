import os
import sys

APP_VERSION = "2.6.2"

# We add src to path so absolute imports within src work cleanly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from workers.telegram_worker import TelegramWorker
import ui.app
from database import init_db, migrate_json_to_db

def main():
    # 0. Windows Taskbar Icon Fix (Set AppUserModelID)
    try:
        if os.name == 'nt':
            import ctypes
            myappid = f'vinodkumar.tgdownloader.{APP_VERSION}'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # -1. Initialize DB and Migrate Legacy Data
    init_db()
    migrate_json_to_db()

    from resource_utils import get_project_root
    env_path = os.path.join(get_project_root(), '.env')
    load_dotenv(dotenv_path=env_path)
    
    api_id_str = os.getenv('API_ID')
    if api_id_str:
        api_id_str = str(api_id_str).strip("'").strip('"')
    
    api_id = int(api_id_str) if api_id_str and api_id_str.isdigit() else 0
    api_hash = (os.getenv('API_HASH') or "").strip("'").strip('"')

    # 1. Initialize our background Telegram Worker (API keys can be supplied later via GUI)
    worker = TelegramWorker(
        session_name='default_session',
        api_id=api_id,
        api_hash=api_hash
    )
    
    # 2. Launch PySide6 UI, giving it the worker and version string
    ui.app.launch_app(worker, APP_VERSION)

if __name__ == "__main__":
    try:
        print("DEBUG: Entry point started")
        main()
    except Exception as e:
        print(f"FATAL ERROR AT ENTRY: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close...") # Hold the terminal open
