"""Friendly Xiaohongshu media downloader entry point."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlparse


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
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


def run_note(arguments: argparse.Namespace) -> int:
    from loguru import logger

    from spider.download_liked_images import save_note_media
    from spider.spider import Data_Spider
    from xhs_utils.common_util import load_or_login_cookies
    from xhs_utils.data_util import check_and_create_path

    try:
        note_url = resolve_xhs_url(arguments.target)
        cookies = load_or_login_cookies(validate=True)
        success, message, note_info = Data_Spider().spider_note(note_url, cookies)
        if not success or not note_info:
            raise RuntimeError(f"笔记详情获取失败: {message}")

        output = Path(arguments.output).resolve() if arguments.output else DEFAULT_NOTE_OUTPUT
        check_and_create_path(output)
        media_count, downloaded_count, original_count, fallback_count = save_note_media(
            note_info,
            output,
            dry_run=arguments.dry_run,
            use_original_images=not arguments.compressed_images,
            overwrite_images=arguments.overwrite_images,
        )
        if not arguments.dry_run:
            metadata_path = output / f"{note_info['note_id']}_info.json"
            metadata_path.write_text(
                json.dumps(note_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        logger.info(
            f"完成：媒体 {media_count} 个，新增下载 {downloaded_count} 个，"
            f"原图 {original_count} 张，预览图回退 {fallback_count} 张；目录：{output}"
        )
        return 0
    except Exception as error:
        logger.exception(f"小红书下载失败: {error}")
        return 1


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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_utf8_console()
    parser = build_parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if arguments.likes:
        if arguments.target:
            parser.error("--likes 模式不需要笔记链接")
        return run_likes(arguments)
    if not arguments.target:
        parser.error("请粘贴小红书笔记链接/分享文字，或使用 --likes")
    return run_note(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
