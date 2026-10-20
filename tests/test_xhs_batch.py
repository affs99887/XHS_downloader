from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from spider.download_batch import DownloadBatch
from spider.download_liked_images import download_note_task, main as likes_main
from xhs_utils.data_util import download_media


class XhsBatchTest(unittest.TestCase):
    def test_persisted_page_failure_resumes_into_the_original_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = Mock()
            api.get_user_self_info2.return_value = (True, "ok", {"data": {"user_id": "user"}})
            api.get_user_like_note_info.return_value = (False, "temporary API failure", {})
            spider = Mock()
            spider.spider_note.return_value = (True, "ok", {"note_id": "abc", "note_type": "图集", "image_list": ["a"]})
            with patch("spider.download_liked_images.load_or_login_cookies", return_value="cookie"), \
                 patch("spider.download_liked_images.XHS_Apis", return_value=api), \
                 patch("spider.download_liked_images.Data_Spider", return_value=spider):
                common = ["--image-filter", "off", "--no-retry", "--delay", "0", "--compressed-images"]
                self.assertEqual(likes_main([*common, "--output", str(root / "original"),
                                             "--log-dir", str(root / "first-log")]), 1)
                manifest = next((root / "first-log").glob("xhs/*/failed_downloads.json"))
                failed = json.loads(manifest.read_text(encoding="utf-8"))["tasks"][0]
                original_media = Path(failed["payload"]["output_root"])
                api.get_user_like_note_info.return_value = (True, "ok", {"data": {"notes": [{"note_id": "abc"}]}})

                def fetch(path, name, *args, **kwargs):
                    (Path(path) / f"{name}.jpg").write_bytes(b"downloaded")
                    return True

                with patch("spider.download_liked_images.download_media_with_fallback", side_effect=fetch):
                    code = likes_main([*common, "--output", str(root / "different"), "--log-dir", str(root / "second-log"),
                                       "--retry-failed", str(manifest)])
                self.assertEqual(code, 0)
                self.assertTrue(list(original_media.glob("*.jpg")))
                self.assertTrue((root / "original" / "downloaded_notes.jsonl").exists())
                self.assertFalse((root / "different" / "downloaded_notes.jsonl").exists())

    def test_likes_limit_does_not_fetch_an_unneeded_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = Mock()
            api.get_user_self_info2.return_value = (True, "ok", {"data": {"user_id": "user"}})
            api.get_user_like_note_info.return_value = (True, "ok", {"data": {
                "notes": [{"note_id": "abc", "xsec_token": "token"}], "has_more": True, "cursor": "next"}})
            spider = Mock()
            spider.spider_note.return_value = (True, "ok", {"note_id": "abc", "note_type": "图集", "image_list": ["a"]})
            with patch("spider.download_liked_images.load_or_login_cookies", return_value="cookie"), \
                 patch("spider.download_liked_images.XHS_Apis", return_value=api), \
                 patch("spider.download_liked_images.Data_Spider", return_value=spider):
                code = likes_main(["--output", str(root / "media"), "--log-dir", str(root / "logs"),
                                   "--limit", "1", "--delay", "0", "--dry-run", "--compressed-images", "--no-retry"])
            self.assertEqual(code, 0)
            self.assertEqual(api.get_user_like_note_info.call_count, 1)

    def test_partial_note_continues_other_images_and_only_marks_complete_after_retry(self):
        note = {"note_id": "abc", "note_type": "图集", "title": "test", "image_list": ["a", "b", "c"]}
        failures = {"b"}
        calls = []

        def fetch(path, name, url, media_type, fallback=None):
            calls.append(url)
            if url in failures:
                raise OSError("timeout")
            (Path(path) / f"{name}.jpg").write_bytes(b"complete")
            return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media, record = root / "media", root / "downloaded_notes.jsonl"
            spider = Mock()
            spider.spider_note.return_value = (True, "ok", note)
            with DownloadBatch("xhs", log_dir=root / "logs", image_filter="off") as batch:
                with patch("spider.download_liked_images.download_media_with_fallback", side_effect=fetch):
                    download_note_task(batch, spider, "cookie", "https://www.xiaohongshu.com/explore/abc", media,
                                       use_original_images=False, record_file=record)
                    self.assertEqual(calls, ["a", "b", "c"])
                    self.assertFalse(record.exists())
                    self.assertEqual(len(batch.failures), 1)
                    failures.clear()
                    with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
                        self.assertEqual(batch.finish(), 0)
                self.assertEqual(calls, ["a", "b", "c", "b"])
                self.assertTrue(record.exists())
                self.assertEqual(len(batch.images), 3)
                self.assertEqual(spider.spider_note.call_count, 1)

    def test_image_download_rejects_html_and_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.jpg"
            path.write_bytes(b"previous image")
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.headers = {}
            response.iter_content.return_value = iter([b"<html>login required</html>"])
            with patch("xhs_utils.data_util.requests.get", return_value=response):
                with self.assertRaises(OSError):
                    download_media(directory, "image", "https://example.test/photo", "image")
            self.assertEqual(path.read_bytes(), b"previous image")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_failed_overwrite_is_retried_even_when_the_old_image_still_exists(self):
        note = {"note_id": "abc", "note_type": "图集", "title": "test", "image_list": ["a"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "abc_image_00_test.jpg"
            media.write_bytes(b"old image")
            spider = Mock()
            spider.spider_note.return_value = (True, "ok", note)
            with DownloadBatch("xhs", log_dir=root / "logs", image_filter="off") as batch:
                calls = []
                def overwrite(*args, **kwargs):
                    calls.append(True)
                    if len(calls) == 1:
                        raise OSError("temporary failure")
                    media.write_bytes(b"new image")
                    return True
                with patch("spider.download_liked_images.download_media_with_fallback",
                           side_effect=overwrite) as fetch:
                    download_note_task(batch, spider, "cookie", "https://www.xiaohongshu.com/explore/abc", root,
                                       use_original_images=False, overwrite_images=True)
                    self.assertTrue(batch.failures)
                    with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
                        self.assertEqual(batch.finish(), 0)
                    self.assertEqual(fetch.call_count, 2)
                    self.assertEqual(media.read_bytes(), b"new image")

    def test_stream_error_does_not_leave_a_partial_video(self):
        def stream(*args, **kwargs):
            yield b"partial video"
            raise OSError("connection reset")

        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {}
        response.iter_content.side_effect = stream
        with tempfile.TemporaryDirectory() as directory:
            with patch("xhs_utils.data_util.requests.get", return_value=response):
                with self.assertRaises(OSError):
                    download_media(directory, "video", "https://example.test/video", "video")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
