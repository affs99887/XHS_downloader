import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

from spider.downloader import run_douyin, run_weibo, run_xhs
from spider.xhs_downloader import extract_xhs_url


class UnifiedDownloaderTest(unittest.TestCase):
    def test_extracts_xhs_link_from_share_text(self):
        self.assertEqual(
            extract_xhs_url("复制打开小红书 https://www.xiaohongshu.com/explore/abc123，"),
            "https://www.xiaohongshu.com/explore/abc123",
        )

    @patch("spider.downloader.run_module", return_value=0)
    def test_routes_douyin_share_text(self, run_module):
        arguments = argparse.Namespace(login=False, target="抖音分享 https://v.douyin.com/a/")
        self.assertEqual(run_douyin(arguments), 0)
        run_module.assert_called_once_with(
            "spider.douyin_downloader",
            ["-u", "抖音分享 https://v.douyin.com/a/"],
        )

    @patch("spider.downloader.run_module", return_value=0)
    def test_routes_multiple_weibo_targets(self, run_module):
        arguments = argparse.Namespace(
            targets=["123", "https://weibo.com/u/456"],
            since_date="7",
            only_original=True,
            set_cookie=False,
        )
        self.assertEqual(run_weibo(arguments), 0)
        run_module.assert_called_once_with(
            "spider.weibo_downloader",
            [
                "-u",
                "123",
                "-u",
                "https://weibo.com/u/456",
                "--since-date",
                "7",
                "--only-original",
            ],
        )

    @patch("spider.downloader.run_module", return_value=0)
    def test_routes_xhs_likes(self, run_module):
        arguments = argparse.Namespace(
            likes=True,
            target=None,
            limit=20,
            output="",
        )
        self.assertEqual(run_xhs(arguments), 0)
        run_module.assert_called_once_with(
            "spider.xhs_downloader",
            ["--likes", "--limit", "20"],
        )

    @patch("spider.downloader.save_weibo_cookie", return_value=Path("weibo_cookie.txt"))
    @patch("spider.downloader.getpass.getpass", return_value="SUB=secret")
    def test_routes_weibo_cookie_setup(self, getpass_mock, save_cookie):
        arguments = argparse.Namespace(
            targets=[],
            since_date=None,
            only_original=False,
            set_cookie=True,
        )

        self.assertEqual(run_weibo(arguments), 0)

        getpass_mock.assert_called_once()
        save_cookie.assert_called_once_with("SUB=secret")


if __name__ == "__main__":
    unittest.main()
