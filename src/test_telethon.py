import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

# We add parent to path so we can import core_downloader
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_downloader import fetch_channel

async def main():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    
    # Use the session file mentioned in gui.py
    session_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "default_session")
    async with TelegramClient(session_path, api_id, api_hash) as client:
        # Testing numeric ID normalization
        # 1866246212 -> should become -1001866246212
        test_id = "1866246212"
        print(f"Searching for channel with ID: {test_id}...")
        
        try:
            channel = await fetch_channel(client, test_id)
            print(f"SUCCESS: Found channel '{channel.title}' (ID: {channel.id})")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == '__main__':
    asyncio.run(main())
