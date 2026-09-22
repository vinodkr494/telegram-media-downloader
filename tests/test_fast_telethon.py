import unittest
import sys
import os
import tempfile
import shutil
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from utils.fast_telethon import (
    fast_download_file,
    CHUNK_SIZE,
    _atomic_finalize_sync,
    _atomic_finalize_async,
    _save_meta,
    _load_meta
)


class MockInputLocation:
    SUBCLASS_OF_ID = 0x1523d462


class MockSender:
    def __init__(self, requested_offsets, chunk_data):
        self.requested_offsets = requested_offsets
        self.chunk_data = chunk_data

    async def send(self, req):
        self.requested_offsets.append(req.offset)
        return type("MockResult", (), {"bytes": self.chunk_data.get(req.offset, b"X" * req.limit)})()


class MockClient:
    def __init__(self, requested_offsets, chunk_data):
        self.requested_offsets = requested_offsets
        self.chunk_data = chunk_data
        self.sender = MockSender(requested_offsets, chunk_data)

    async def _borrow_exported_sender(self, dc_id):
        return self.sender

    async def _return_exported_sender(self, sender):
        pass

    async def __call__(self, req):
        self.requested_offsets.append(req.offset)
        return type("MockResult", (), {"bytes": self.chunk_data.get(req.offset, b"X" * req.limit)})()


class TestFastTelethon(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_chunk_size_validity(self):
        self.assertEqual(CHUNK_SIZE, 512 * 1024)

    def test_zero_size_guard(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(fast_download_file(None, None, "dummy.mp4", 0))
        self.assertFalse(res)
        loop.close()

    def test_atomic_finalize_sync(self):
        part_path = os.path.join(self.temp_dir, "test.mp4.part")
        target_path = os.path.join(self.temp_dir, "test.mp4")
        meta_path = part_path + ".meta"

        with open(part_path, "wb") as f:
            f.write(b"video payload data")
        with open(meta_path, "w") as f:
            f.write("{}")

        success = _atomic_finalize_sync(part_path, target_path, meta_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_path))
        self.assertFalse(os.path.exists(part_path))
        self.assertFalse(os.path.exists(meta_path))

    def test_complete_part_file_instant_finalization(self):
        target_path = os.path.join(self.temp_dir, "video.mp4")
        part_path = target_path + ".part"
        meta_path = part_path + ".meta"
        file_size = CHUNK_SIZE * 2

        with open(part_path, "wb") as f:
            f.truncate(file_size)

        _save_meta(meta_path, file_size, CHUNK_SIZE, 2, {0, 1})

        loop = asyncio.new_event_loop()
        loc = MockInputLocation()
        success = loop.run_until_complete(
            fast_download_file(None, loc, target_path, file_size, dc_id=1, workers=2)
        )
        loop.close()

        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_path))
        self.assertFalse(os.path.exists(part_path))
        self.assertFalse(os.path.exists(meta_path))

    def test_partial_resume_only_downloads_missing_chunks(self):
        target_path = os.path.join(self.temp_dir, "resumable.mp4")
        part_path = target_path + ".part"
        meta_path = part_path + ".meta"
        file_size = CHUNK_SIZE * 3  # 3 parts: 0, 1, 2

        # Pre-allocate and mark part 0 and 2 as already completed
        with open(part_path, "wb") as f:
            f.truncate(file_size)
            f.seek(0)
            f.write(b"A" * CHUNK_SIZE)
            f.seek(CHUNK_SIZE * 2)
            f.write(b"C" * CHUNK_SIZE)

        _save_meta(meta_path, file_size, CHUNK_SIZE, 3, {0, 2})

        requested_offsets = []
        chunk_data = {CHUNK_SIZE: b"B" * CHUNK_SIZE}
        client = MockClient(requested_offsets, chunk_data)
        loc = MockInputLocation()

        loop = asyncio.new_event_loop()
        success = loop.run_until_complete(
            fast_download_file(client, loc, target_path, file_size, dc_id=1, workers=2)
        )
        loop.close()

        self.assertTrue(success)
        self.assertEqual(requested_offsets, [CHUNK_SIZE], "Only missing chunk (part 1) should have been requested")
        self.assertTrue(os.path.exists(target_path))
        self.assertEqual(os.path.getsize(target_path), file_size)

    def test_cancel_saves_meta_and_allows_resume(self):
        target_path = os.path.join(self.temp_dir, "cancel_test.mp4")
        part_path = target_path + ".part"
        meta_path = part_path + ".meta"
        file_size = CHUNK_SIZE * 4

        cancel_event = asyncio.Event()

        class CancellingSender(MockSender):
            async def send(self, req):
                cancel_event.set()
                return await super().send(req)

        class CancellingClient(MockClient):
            def __init__(self, requested_offsets, chunk_data):
                super().__init__(requested_offsets, chunk_data)
                self.sender = CancellingSender(requested_offsets, chunk_data)

            async def __call__(self, req):
                cancel_event.set()
                return await super().__call__(req)

        requested_offsets = []
        chunk_data = {i * CHUNK_SIZE: b"D" * CHUNK_SIZE for i in range(4)}
        client = CancellingClient(requested_offsets, chunk_data)
        loc = MockInputLocation()

        loop = asyncio.new_event_loop()
        # First run gets cancelled
        res1 = loop.run_until_complete(
            fast_download_file(client, loc, target_path, file_size, dc_id=1, cancel_event=cancel_event, workers=2)
        )
        self.assertFalse(res1)
        self.assertTrue(os.path.exists(part_path))
        self.assertTrue(os.path.exists(meta_path))

        # Meta should contain at least 1 completed part
        saved_parts = _load_meta(meta_path, file_size, 4)
        self.assertGreaterEqual(len(saved_parts), 1)

        # Now resume without cancel
        requested_offsets.clear()
        normal_client = MockClient(requested_offsets, chunk_data)
        res2 = loop.run_until_complete(
            fast_download_file(normal_client, loc, target_path, file_size, dc_id=1, workers=2)
        )
        loop.close()

        self.assertTrue(res2)
        self.assertTrue(os.path.exists(target_path))
        self.assertFalse(os.path.exists(part_path))
        self.assertFalse(os.path.exists(meta_path))

    def test_preallocated_part_without_meta_is_not_falsely_finalized(self):
        target_path = os.path.join(self.temp_dir, "prealloc.mp4")
        part_path = target_path + ".part"
        meta_path = part_path + ".meta"
        file_size = CHUNK_SIZE * 2

        # Part file exists and is full size due to OS preallocation/truncation, but NO meta exists
        with open(part_path, "wb") as f:
            f.truncate(file_size)

        requested_offsets = []
        chunk_data = {0: b"1" * CHUNK_SIZE, CHUNK_SIZE: b"2" * CHUNK_SIZE}
        client = MockClient(requested_offsets, chunk_data)
        loc = MockInputLocation()

        loop = asyncio.new_event_loop()
        success = loop.run_until_complete(
            fast_download_file(client, loc, target_path, file_size, dc_id=1, workers=2)
        )
        loop.close()

        self.assertTrue(success)
        # All chunks should have been requested because missing meta means 0 completed parts
        self.assertEqual(sorted(requested_offsets), [0, CHUNK_SIZE])
        self.assertTrue(os.path.exists(target_path))

    def test_worker_cancellation_on_error_prevents_io_error(self):
        target_path = os.path.join(self.temp_dir, "error_test.mp4")
        file_size = CHUNK_SIZE * 4

        class FailingSender(MockSender):
            async def send(self, req):
                if req.offset == 0:
                    raise RuntimeError("Simulated network drop")
                await asyncio.sleep(0.1)
                return await super().send(req)

        class FailingClient(MockClient):
            def __init__(self, requested_offsets, chunk_data):
                super().__init__(requested_offsets, chunk_data)
                self.sender = FailingSender(requested_offsets, chunk_data)

            async def __call__(self, req):
                if req.offset == 0:
                    raise RuntimeError("Simulated network drop")
                await asyncio.sleep(0.1)
                return await super().__call__(req)

        requested_offsets = []
        chunk_data = {i * CHUNK_SIZE: b"X" * CHUNK_SIZE for i in range(4)}
        client = FailingClient(requested_offsets, chunk_data)
        loc = MockInputLocation()

        loop = asyncio.new_event_loop()
        with self.assertRaises(RuntimeError):
            loop.run_until_complete(
                fast_download_file(client, loc, target_path, file_size, dc_id=1, workers=2)
            )
        loop.close()

        self.assertFalse(os.path.exists(target_path))


if __name__ == "__main__":
    unittest.main()

