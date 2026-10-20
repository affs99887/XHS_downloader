"""Friendly Xiaohongshu media downloader entry point."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlparse

from spider.download_batch import DownloadBatch, add_batch_options, batch_option_arguments, read_failure_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTE_OUTPUT = PROJECT_ROOT / "download_files" / "xhs" / "notes"
DEFAULT_LIKES_OUTPUT = PROJECT_ROOT / "download_files" / "xhs" / "likes"

_XHS_URL_RE = re.compile(
    r"(?P<url>(?:https?://)?(?:www\.)?(?:xiaohongshu\.com|xhslink\.com)/[^\s]+)",
    re.IGNORECASE,
)
_URL_TRAILING_PUNCTUATION = "，。；;！!）》】]}>'\""


def configure_utf8_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("XHS_QR_FULL_BLOCK", "1")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def extract_xhs_url(value: str) -> str:
    """Extract a Xiaohongshu URL from copied share text."""
    match = _XHS_URL_RE.search(value.strip())
    if not match:
        raise ValueError("没有找到小红书链接，请粘贴笔记链接或完整分享文字")
    url = match.group("url").rstrip(_URL_TRAILING_PUNCTUATION)
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def resolve_xhs_url(value: str) -> str:
    """Resolve xhslink.com short links to a note URL."""
    url = extract_xhs_url(value)
    hostname = (urlparse(url).hostname or "").lower()
    if hostname == "xhslink.com" or hostname.endswith(".xhslink.com"):
        import requests

        response = requests.get(
            url,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/136.0.0.0 Safari/537.36"
                )
            },
            timeout=15,
        )
        response.raise_for_status()
        url = response.url
    return url


def run_likes(arguments: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "spider.download_liked_images",
        "--output",
        str(Path(arguments.output).resolve() if arguments.output else DEFAULT_LIKES_OUTPUT),
    ]
    if arguments.limit:
        command.extend(["--limit", str(arguments.limit)])
    if arguments.dry_run:
        command.append("--dry-run")
    if arguments.compressed_images:
        command.append("--compressed-images")
    if arguments.overwrite_images:
        command.append("--overwrite-images")
    if arguments.continue_past_downloaded:
        command.append("--continue-past-downloaded")
    command.extend(batch_option_arguments(arguments))
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


def run_note(arguments: argparse.Namespace) -> int:
    from spider.download_liked_images import download_note_task
    from spider.spider import Data_Spider
    from xhs_utils.common_util import load_or_login_cookies
    with DownloadBatch.from_arguments("xhs", arguments) as batch:
        def run():
            cookies = load_or_login_cookies(validate=True)
            data_spider = Data_Spider()
            if arguments.retry_failed:
                tasks = read_failure_tasks(arguments.retry_failed, "xhs")
                for task in tasks:
                    payload = task["payload"]
                    if payload["kind"] == "xhs_start":
                        url = resolve_xhs_url(payload["target"])
                        output = Path(payload.get("output_root") or arguments.output or DEFAULT_NOTE_OUTPUT).resolve()
                        download_note_task(batch, data_spider, cookies, url, output,
                                           dry_run=arguments.dry_run,
                                           use_original_images=not arguments.compressed_images)
                        continue
                    if payload["kind"] != "xhs_note":
                        raise ValueError("喜欢列表的分页失败请使用 --likes --retry-failed 重试")
                    download_note_task(batch, data_spider, cookies, payload["note_url"],
                                       Path(payload["output_root"]), dry_run=arguments.dry_run,
                                       use_original_images=payload.get("use_original_images", True),
                                       record_file=payload.get("record_file"), retry_paths=payload.get("retry_paths"))
            else:
                note_url = resolve_xhs_url(arguments.target)
                output = Path(arguments.output).resolve() if arguments.output else DEFAULT_NOTE_OUTPUT
                download_note_task(batch, data_spider, cookies, note_url, output,
                                   dry_run=arguments.dry_run,
                                   use_original_images=not arguments.compressed_images,
                                   overwrite_images=arguments.overwrite_images)

        batch.attempt("xhs_start", "准备小红书下载",
                      {"kind": "xhs_start", "target": arguments.target,
                       "output_root": str(Path(arguments.output).resolve() if arguments.output else DEFAULT_NOTE_OUTPUT)}, run)
        return batch.finish(dry_run=arguments.dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="下载小红书单条笔记，或当前账号的喜欢列表"
    )
    parser.add_argument("target", nargs="?", help="笔记链接或完整分享文字")
    parser.add_argument("--likes", action="store_true", help="下载当前账号的喜欢列表")
    parser.add_argument("--limit", type=int, default=0, help="喜欢列表最多处理几条；0 为全部")
    parser.add_argument("--output", default="", help="自定义输出目录")
    parser.add_argument("--dry-run", action="store_true", help="只获取信息，不下载媒体")
    parser.add_argument(
        "--compressed-images",
        action="store_true",
        help="下载预览图，不转换为原图地址",
    )
    parser.add_argument(
        "--overwrite-images",
        action="store_true",
        help="覆盖已经存在的图片",
    )
    parser.add_argument(
        "--continue-past-downloaded",
        action="store_true",
        help="喜欢列表遇到已下载笔记后继续向后扫描",
    )
    add_batch_options(parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_utf8_console()
    parser = build_parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if arguments.likes:
        if arguments.target:
            parser.error("--likes 模式不需要笔记链接")
        return run_likes(arguments)
    if not arguments.target and not arguments.retry_failed:
        parser.error("请粘贴小红书笔记链接/分享文字，或使用 --likes")
    return run_note(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
