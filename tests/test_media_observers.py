from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spider.download_batch import DownloadBatch
from spider.media_observers import douyin_retry_arguments, observe_weibo


class FakeWeibo:
    def __init__(self):
        self.fail_file = True
        self.fail_user = True
        self.user_config = {"user_id": "123"}
        self.user = {}
        self.query = ""

    def initialize_info(self, config):
        self.user_config = config
        self.user = {}

    def get_pages(self):
        if not self.fail_user:
            self.user = {"id": "123"}

    def download_one_file(self, url, path, media_type, weibo_id, created_at):
        # Upstream swallows errors and returns None in both cases.
        if not self.fail_file:
            Path(path).with_suffix(".png").write_bytes(b"complete image")


class MediaObserverTest(unittest.TestCase):
    def test_weibo_user_retry_keeps_observing_media_after_initial_scope_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            class ReplayWeibo(FakeWeibo):
                def get_pages(self):
                    if not self.fail_user:
                        self.user = {"id": "123"}
                        self.download_one_file("https://example.test/a", str(root / "a.jpg"), "img", "123", "date")

            crawler = ReplayWeibo()
            with DownloadBatch("weibo", log_dir=root / "logs", image_filter="off") as batch:
                with observe_weibo(ReplayWeibo, batch, root):
                    crawler.get_pages()
                crawler.fail_user = False
                list(batch.retries.values())[0]()
                self.assertTrue(any(key.startswith("weibo_media:") for key in batch.failures))
                self.assertFalse(any(key.startswith("weibo_user:") for key in batch.failures))
                crawler.fail_file = False
                with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
                    self.assertEqual(batch.finish(), 0)
                self.assertIn(root / "a.png", batch.images)

    def test_weibo_handles_swallowed_failures_and_changed_image_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = FakeWeibo.download_one_file
            crawler = FakeWeibo()
            with DownloadBatch("weibo", log_dir=root / "logs", image_filter="off") as batch:
                with observe_weibo(FakeWeibo, batch, root):
                    crawler.download_one_file("https://example.test/a", str(root / "a.jpg"), "img", "123", "date")
                    crawler.get_pages()
                    self.assertEqual(len(batch.failures), 2)
                    crawler.fail_file = crawler.fail_user = False
                    with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
                        self.assertEqual(batch.finish(), 0)
                    self.assertIn(root / "a.png", batch.images)
            self.assertIs(FakeWeibo.download_one_file, original)

    def test_douyin_retries_only_failed_target_while_preserving_config_and_path(self):
        arguments = ["--config", "custom.yml", "-u", "profile1", "--url=profile2", "--path", "custom output"]
        self.assertEqual(douyin_retry_arguments(arguments, "failed_video"),
                         ["--config", "custom.yml", "--path", "custom output", "-u", "failed_video"])

    def test_douyin_repeated_failure_is_not_duplicated_as_a_url_failure(self):
        import asyncio
        from types import SimpleNamespace
        from spider.douyin_downloader import activate_vendor
        activate_vendor()
        from cli import main as cli
        from core.downloader_base import BaseDownloader, DownloadResult
        from storage.file_manager import FileManager
        from spider.media_observers import observe_douyin

        aweme_id = "1234567890123456789"
        instance = SimpleNamespace(progress_reporter=None)
        attempts = []

        async def download(url, *args, **kwargs):
            attempts.append(url)
            result = DownloadResult()
            result.total = 1
            status = "failed" if len(attempts) < 3 else "success"
            if status == "failed":
                result.failed = 1
            else:
                result.success = 1
            BaseDownloader._progress_advance_item(instance, status, aweme_id)
            return result

        def invoke(arguments):
            asyncio.run(cli.download_url(arguments[-1]))

        with tempfile.TemporaryDirectory() as directory:
            with DownloadBatch("douyin", log_dir=Path(directory), image_filter="off") as batch:
                with patch.object(cli, "download_url", download):
                    with observe_douyin(batch, ["--path", "custom"], invoke):
                        existing = Path(directory) / "existing.jpg"
                        existing.write_bytes(b"already downloaded")
                        manager = SimpleNamespace(base_path=Path(directory))
                        self.assertEqual(asyncio.run(FileManager.download_file(manager, "https://example.test/a", existing,
                                                                               return_saved_path=True)), existing)
                        asyncio.run(cli.download_url("https://www.douyin.com/user/example"))
                        self.assertEqual(list(batch.failures), [f"douyin_aweme:{aweme_id}"])
                        self.assertTrue(asyncio.run(BaseDownloader._should_download(instance, aweme_id)))
                        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y") as prompt:
                            self.assertEqual(batch.finish(), 0)
                        self.assertEqual(prompt.call_count, 2)
                        self.assertEqual(len(attempts), 3)


if __name__ == "__main__":
    unittest.main()
