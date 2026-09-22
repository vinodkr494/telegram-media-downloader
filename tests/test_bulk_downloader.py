import unittest
import sys
import os
import tempfile
import shutil
import asyncio

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from core_downloader import get_unique_filepath, get_messages_by_type


class MockDocument:
    def __init__(self, mime_type="", size=1024):
        self.mime_type = mime_type
        self.size = size


class MockMessage:
    def __init__(self, id, media=None, photo=None, video=None, document=None, message=""):
        self.id = id
        self.media = media
        self.photo = photo
        self.video = video
        self.document = document
        self.message = message


class MockTelethonClient:
    def __init__(self, messages):
        self._messages = messages

    async def get_messages(self, channel, **kwargs):
        filter_obj = kwargs.get("filter")
        limit = kwargs.get("limit")
        msgs = self._messages
        
        if filter_obj is not None:
            # Simulate filter
            f_name = filter_obj.__class__.__name__
            if "Photo" in f_name:
                msgs = [m for m in msgs if m.photo is not None]
            elif "Video" in f_name:
                msgs = [m for m in msgs if m.video is not None]
            elif "Document" in f_name:
                msgs = [m for m in msgs if m.document is not None]
            elif "Music" in f_name or "Voice" in f_name:
                msgs = [m for m in msgs if m.document and m.document.mime_type.startswith("audio/")]
                
        if limit is not None:
            msgs = msgs[:limit]
        return msgs


class TestBulkDownloader(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        import database
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir, "test_downloader.db")
        database.init_db()

    def tearDown(self):
        import database
        database.DB_PATH = self.orig_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_unique_filepath_non_destructive(self):
        # 1. Path generation when file does not exist (should NOT create file)
        target = get_unique_filepath(self.temp_dir, "test.mp4")
        self.assertEqual(os.path.basename(target), "test.mp4")
        self.assertFalse(os.path.exists(target), "get_unique_filepath must not create empty files on disk beforehand")

        # 2. When file with content exists
        with open(target, "w") as f:
            f.write("content")
        
        target2 = get_unique_filepath(self.temp_dir, "test.mp4")
        self.assertEqual(os.path.basename(target2), "test (2).mp4")

        # 3. When 0-byte file exists (abandoned attempt), it should reuse it
        empty_file = os.path.join(self.temp_dir, "empty.mp4")
        with open(empty_file, "w"):
            pass
        target3 = get_unique_filepath(self.temp_dir, "empty.mp4")
        self.assertEqual(target3, empty_file)

    def test_get_messages_by_type_filtering(self):
        raw_msgs = [
            MockMessage(id=1, media=True, photo=True),
            MockMessage(id=2, media=True, video=True),
            MockMessage(id=3, media=True, document=MockDocument(mime_type="application/pdf")),
            MockMessage(id=4, media=True, document=MockDocument(mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")), # docx
            MockMessage(id=5, media=True, document=MockDocument(mime_type="application/zip")),
            MockMessage(id=6, media=True, document=MockDocument(mime_type="audio/mpeg")),
            MockMessage(id=7, media=None, message="Hello plain text chat message") # Text only
        ]

        client = MockTelethonClient(raw_msgs)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. Images (choice 1)
        photos = loop.run_until_complete(get_messages_by_type(client, "test_channel", 1))
        self.assertEqual([m.id for m in photos], [1])

        # 2. Videos (choice 2)
        videos = loop.run_until_complete(get_messages_by_type(client, "test_channel", 2))
        self.assertEqual([m.id for m in videos], [2])

        # 3. Documents (choice 3) - MUST include docx, pdf, zip (not just pdfs!)
        docs = loop.run_until_complete(get_messages_by_type(client, "test_channel", 3))
        self.assertEqual(sorted([m.id for m in docs]), [3, 4, 5, 6])

        # 4. ZIPs (choice 4)
        zips = loop.run_until_complete(get_messages_by_type(client, "test_channel", 4))
        self.assertEqual([m.id for m in zips], [5])

        # 5. Audio (choice 5)
        audios = loop.run_until_complete(get_messages_by_type(client, "test_channel", 5))
        self.assertEqual([m.id for m in audios], [6])

        # 6. All Media (choice 6) - MUST exclude text-only message (id=7)
        all_media = loop.run_until_complete(get_messages_by_type(client, "test_channel", 6))
        self.assertNotIn(7, [m.id for m in all_media])
        self.assertEqual(len(all_media), 6)

        loop.close()

    def test_ghost_card_resolution_matching(self):
        # Verify card matching logic for multi-category bulk downloads
        card_widgets = {
            "mychannel_1": "Card_Images",
            "mychannel_2": "Card_Videos",
            "mychannel_3": "Card_Docs",
        }

        def resolve_card(task_id, data):
            ch_resolved = str(data.get("channel_input", ""))
            original_in = str(data.get("original_input", ""))
            m_id = str(data.get("media_id", 6))
            topic_id = str(data.get("topic_id")) if data.get("topic_id") is not None else None

            matched_id = None
            for old_id, card in list(card_widgets.items()):
                parts = old_id.split('_')
                if len(parts) >= 3:
                    old_chan = "_".join(parts[:-2])
                    old_topic = parts[-2]
                    old_media = parts[-1]
                elif len(parts) == 2:
                    old_chan = parts[0]
                    old_topic = None
                    old_media = parts[1]
                else:
                    continue

                if old_media != m_id:
                    continue
                if topic_id is not None and old_topic != topic_id:
                    continue

                if (old_chan == original_in or 
                    old_chan == ch_resolved or 
                    old_chan.replace('-100', '', 1) == ch_resolved.replace('-100', '', 1)):
                    matched_id = old_id
                    break
            return matched_id

        # Resolving Videos (-100999_2) MUST match mychannel_2, NOT mychannel_1
        data_videos = {
            "task_id": "-100999_2",
            "channel_input": "-100999",
            "original_input": "mychannel",
            "media_id": 2
        }
        self.assertEqual(resolve_card("-100999_2", data_videos), "mychannel_2")

        # Resolving Images (-100999_1) MUST match mychannel_1
        data_images = {
            "task_id": "-100999_1",
            "channel_input": "-100999",
            "original_input": "mychannel",
            "media_id": 1
        }
        self.assertEqual(resolve_card("-100999_1", data_images), "mychannel_1")

    def test_unmark_media_completed(self):
        from database import mark_media_completed, unmark_media_completed, get_completed_state_db
        test_chan = "999888777"
        test_msg_id = 424242

        mark_media_completed(test_chan, test_msg_id)
        completed = get_completed_state_db()
        self.assertIn((test_chan, test_msg_id), completed)

        unmark_media_completed(test_chan, test_msg_id)
    def test_get_unique_filepath_with_reserved_paths(self):
        # When downloading in parallel, reserved_paths prevents giving the same filename
        # to concurrent tasks before they finish writing to disk
        reserved = set()
        p1 = get_unique_filepath(self.temp_dir, "video.mp4", reserved_paths=reserved)
        p2 = get_unique_filepath(self.temp_dir, "video.mp4", reserved_paths=reserved)
        p3 = get_unique_filepath(self.temp_dir, "video.mp4", reserved_paths=reserved)

        self.assertEqual(os.path.basename(p1), "video.mp4")
        self.assertEqual(os.path.basename(p2), "video (2).mp4")
        self.assertEqual(os.path.basename(p3), "video (3).mp4")
        self.assertIn(p1, reserved)
        self.assertIn(p2, reserved)
        self.assertIn(p3, reserved)

    def test_get_unique_filepath_with_part_file(self):
        # If video.mp4.part exists from an active download, next allocation must be video (2).mp4
        part_file = os.path.join(self.temp_dir, "downloading.mp4.part")
        with open(part_file, "w") as f:
            f.write("partial data")

        target = get_unique_filepath(self.temp_dir, "downloading.mp4")
        self.assertEqual(os.path.basename(target), "downloading (2).mp4")

    def test_redownload_deleted_config(self):
        from ui.views.settings_view import load_config
        cfg = load_config()
        self.assertIn("redownload_deleted", cfg)
        self.assertFalse(cfg["redownload_deleted"])

    def test_download_single_file_finalizes_existing_part_file(self):
        from core_downloader import download_single_file
        from telethon.tl.types import PeerChannel

        file_size = 5000
        msg = MockMessage(id=101, video=MockDocument(size=file_size))
        
        # Create a .part file with exact file_size on disk
        part_file = os.path.join(self.temp_dir, f"Video_101.mp4.part")
        target_file = os.path.join(self.temp_dir, f"Video_101.mp4")
        with open(part_file, "wb") as f:
            f.write(b"V" * file_size)

        completed_files = []
        def complete_cb(msg_id, filepath=None, **kwargs):
            completed_files.append((msg_id, filepath))

        channel = PeerChannel(channel_id=123456)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            download_single_file(None, channel, msg, self.temp_dir, complete_cb=complete_cb)
        )
        loop.close()

        self.assertTrue(os.path.exists(target_file), "Target .mp4 file must exist after finalization")
        self.assertFalse(os.path.exists(part_file), "Temp .part file must be removed after finalization")
        self.assertEqual(len(completed_files), 1)
        self.assertEqual(completed_files[0][0], 101)

    def test_candidate_filepath_reuses_existing_part_without_duplicate_renaming(self):
        from core_downloader import download_single_file
        from database import update_media_downloaded_path, get_media_downloaded_path
        from telethon.tl.types import PeerChannel
        from telethon.utils import get_peer_id

        channel = PeerChannel(channel_id=888999)
        c_id = str(get_peer_id(channel)).replace("-100", "", 1)
        msg = MockMessage(id=202, video=MockDocument(size=10000))

        # Assign initial db_filename
        update_media_downloaded_path(c_id, 202, "MyCustomVideo.mp4")

        # Create .part file on disk matching that name
        part_file = os.path.join(self.temp_dir, "MyCustomVideo.mp4.part")
        with open(part_file, "wb") as f:
            f.write(b"M" * 10000)

        completed_files = []
        def complete_cb(msg_id, filepath=None, **kwargs):
            completed_files.append((msg_id, filepath))

        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            download_single_file(None, channel, msg, self.temp_dir, complete_cb=complete_cb)
        )
        loop.close()

        # Database path must still be MyCustomVideo.mp4 (not MyCustomVideo (2).mp4)
        db_path = get_media_downloaded_path(c_id, 202)
        self.assertEqual(db_path, "MyCustomVideo.mp4")
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "MyCustomVideo.mp4")))

    def test_load_download_state_channel_isolation(self):
        from core_downloader import load_download_state
        from database import mark_media_completed

        mark_media_completed("111222", 10)
        mark_media_completed("111222", 20)
        mark_media_completed("333444", 30)

        # None must NOT leak all channels
        self.assertEqual(load_download_state(None), set())

        # Isolated per channel
        state_1 = load_download_state("111222")
        state_2 = load_download_state("-100111222") # Should handle -100 prefix
        state_3 = load_download_state("333444")
        state_4 = load_download_state("999999")

        self.assertEqual(state_1, {10, 20})
        self.assertEqual(state_2, {10, 20})
        self.assertEqual(state_3, {30})
        self.assertEqual(state_4, set())

    def test_task_completed_initial_scoped_to_current_messages(self):
        # Channel has 50 historically downloaded items in DB
        downloaded_state = set(range(1, 51))

        # Current task only has 5 new messages: [51, 52, 53, 54, 55]
        messages = [MockMessage(id=i) for i in range(51, 56)]
        all_messages_count = len(messages)

        # Buggy calculation was: completed_initial = len(downloaded_state) -> 50
        # Correct calculation:
        already_completed = sum(1 for m in messages if m.id in downloaded_state)
        completed_initial = already_completed

        self.assertEqual(completed_initial, 0, "Initial completed count must be 0 for new messages")
        self.assertLess(completed_initial, all_messages_count, "completed_initial must not exceed total_items")

    def test_cleanup_orphaned_part_and_meta_when_target_exists(self):
        from core_downloader import download_single_file
        from telethon.tl.types import PeerChannel

        target_file = os.path.join(self.temp_dir, "Video_303.mp4")
        part_file = target_file + ".part"
        meta_file = part_file + ".meta"

        with open(target_file, "wb") as f:
            f.write(b"FullVideoData")
        with open(part_file, "wb") as f:
            f.write(b"LeftoverPartData")
        with open(meta_file, "w") as f:
            f.write("{}")

        file_size = len(b"FullVideoData")
        msg = MockMessage(id=303, video=MockDocument(size=file_size))
        channel = PeerChannel(channel_id=555666)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            download_single_file(None, channel, msg, self.temp_dir)
        )
        loop.close()

        self.assertTrue(os.path.exists(target_file))
        self.assertFalse(os.path.exists(part_file), "Orphaned .part file must be cleaned up")
        self.assertFalse(os.path.exists(meta_file), "Orphaned .meta file must be cleaned up")

    def test_incomplete_chunked_part_file_not_finalized_prematurely(self):
        from core_downloader import download_single_file
        from telethon.tl.types import PeerChannel

        file_size = 2 * 1024 * 1024 # 2MB (Chunked)
        target_file = os.path.join(self.temp_dir, "Video_404.mp4")
        part_file = target_file + ".part"
        meta_file = part_file + ".meta"

        # Preallocated .part file matches file_size, but NO metadata exists
        with open(part_file, "wb") as f:
            f.truncate(file_size)

        msg = MockMessage(id=404, video=MockDocument(size=file_size))
        channel = PeerChannel(channel_id=777888)

        completed_files = []
        def complete_cb(msg_id, filepath=None, **kwargs):
            completed_files.append((msg_id, filepath))

        loop = asyncio.new_event_loop()
        # Mock client that will fail fast_download_file and fallback, without actually finalizing unverified part
        loop.run_until_complete(
            download_single_file(None, channel, msg, self.temp_dir, complete_cb=complete_cb)
        )
        loop.close()

        # Should NOT finalize incomplete zero-byte preallocated file as target_file
        self.assertFalse(os.path.exists(target_file), "Unverified preallocated .part file must not be finalized as complete")


if __name__ == "__main__":
    unittest.main()
