import os
import sys

# We add src to path so absolute imports within src work cleanly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from workers.telegram_worker import TelegramWorker
import ui.app

def main():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(dotenv_path=env_path)
    
    api_id_str = os.getenv('API_ID')
    api_id = int(api_id_str) if api_id_str and api_id_str.isdigit() else 0
    api_hash = os.getenv('API_HASH') or ""

    # 1. Initialize our background Telegram Worker (API keys can be supplied later via GUI)
    worker = TelegramWorker(
        session_name='default_session',
        api_id=api_id,
        api_hash=api_hash
    )
    
    # 2. Launch PySide6 UI, giving it the worker to communicate with
    ui.app.launch_app(worker)

if __name__ == "__main__":
    main()
