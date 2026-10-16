import unittest

from spider.douyin_downloader import (
    extract_douyin_url,
    has_option,
    normalize_url_arguments,
)


class DouyinEntrypointTest(unittest.TestCase):
    def test_extracts_short_url_from_share_message(self):
        share_message = (
            "3.14 复制打开抖音，看看作品 "
            "https://v.douyin.com/AbCdEfGh/ 复制此链接，打开抖音搜索"
        )

        self.assertEqual(
            extract_douyin_url(share_message),
            "https://v.douyin.com/AbCdEfGh/",
        )

    def test_preserves_regular_url_argument(self):
        arguments = normalize_url_arguments(
            ["-u", "https://www.douyin.com/video/123456789", "-t", "3"]
        )

        self.assertEqual(
            arguments,
            ["-u", "https://www.douyin.com/video/123456789", "-t", "3"],
        )

    def test_normalizes_long_url_assignment(self):
        arguments = normalize_url_arguments(
            ["--url=口令 https://www.douyin.com/note/123456789，"]
        )

        self.assertEqual(
            arguments,
            ["--url=https://www.douyin.com/note/123456789"],
        )

    def test_detects_short_and_long_options(self):
        self.assertTrue(has_option(["-c", "custom.yml"], "-c", "--config"))
        self.assertTrue(
            has_option(["--config=custom.yml"], "-c", "--config")
        )
        self.assertFalse(has_option(["-u", "https://v.douyin.com/a/"], "-c", "--config"))


if __name__ == "__main__":
    unittest.main()
