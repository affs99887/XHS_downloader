import argparse
import os
import tempfile
import unittest
from pathlib import Path

from spider.weibo_downloader import (
    VENDOR_ROOT,
    _date_or_days,
    apply_overrides,
    extract_weibo_user_id,
    has_crawl_targets,
    normalize_config,
)


class WeiboEntrypointTest(unittest.TestCase):
    def test_normalizes_paths_relative_to_config(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "weibo.json"
            config = {
                "user_id_list": "users.txt",
                "cookie": "cookie.txt",
                "sqlite_db_path": "data/weibo.db",
                "output_directory": "downloads",
            }

            normalized = normalize_config(config, config_path)

            self.assertEqual(
                normalized["user_id_list"],
                str((config_path.parent / "users.txt").resolve()),
            )
            self.assertEqual(
                normalized["cookie"],
                str((config_path.parent / "cookie.txt").resolve()),
            )
            self.assertEqual(
                normalized["sqlite_db_path"],
                str((config_path.parent / "data/weibo.db").resolve()),
            )
            self.assertEqual(
                normalized["output_directory"],
                os.path.relpath(
                    (config_path.parent / "downloads").resolve(),
                    VENDOR_ROOT.resolve(),
                ),
            )

    def test_cli_user_ids_override_config(self):
        arguments = argparse.Namespace(
            user_ids=["123", " 456 "],
            since_date="7",
            end_date=None,
            only_original=True,
        )

        overridden = apply_overrides(
            {"user_id_list": ["old"], "since_date": "2020-01-01"},
            arguments,
        )

        self.assertEqual(overridden["user_id_list"], ["123", "456"])
        self.assertEqual(overridden["since_date"], 7)
        self.assertEqual(overridden["only_crawl_original"], 1)

    def test_date_or_days_keeps_date_and_converts_integer(self):
        self.assertEqual(_date_or_days("2026-07-01"), "2026-07-01")
        self.assertEqual(_date_or_days(" 30 "), 30)

    def test_requires_at_least_one_target(self):
        self.assertFalse(has_crawl_targets({"user_id_list": []}))
        self.assertTrue(has_crawl_targets({"user_id_list": ["123"]}))
        self.assertTrue(has_crawl_targets({"user_id_list": "users.txt"}))

    def test_accepts_weibo_uid_profile_and_post_url(self):
        self.assertEqual(extract_weibo_user_id("123456"), "123456")
        self.assertEqual(
            extract_weibo_user_id("https://weibo.com/u/123456"),
            "123456",
        )
        self.assertEqual(
            extract_weibo_user_id("https://weibo.com/123456/AbCdEf"),
            "123456",
        )
        self.assertEqual(
            extract_weibo_user_id(
                "复制微博内容 https://weibo.com/123456/AbCdEf，打开查看"
            ),
            "123456",
        )

    def test_rejects_detail_url_without_uid(self):
        with self.assertRaisesRegex(ValueError, "UID"):
            extract_weibo_user_id("https://m.weibo.cn/detail/123456")


if __name__ == "__main__":
    unittest.main()
