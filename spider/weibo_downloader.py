"""Project entry point for the vendored dataabc/weibo-crawler.

The upstream project expects ``config.json`` beside ``weibo.py`` and imports
top-level modules such as ``const`` and ``util``.  This wrapper keeps the
upstream source isolated under ``vendor/weibo_crawler`` while allowing runtime
configuration to live at the project root.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import os
import re
import shutil
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "weibo_crawler"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "weibo_config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "weibo_config.example.json"
_WEIBO_URL_RE = re.compile(
    r"(?P<url>https?://(?:www\.)?(?:weibo\.com|m\.weibo\.cn)/[^\s]+)",
    re.IGNORECASE,
)
_URL_TRAILING_PUNCTUATION = "，。；;！!）》】]}>'\""


def extract_weibo_user_id(value: Any) -> str:
    """Accept a UID, user profile URL, or a desktop post URL containing UID."""
    target = str(value).strip()
    if target.isdecimal():
        return target

    if not target.lower().startswith(("http://", "https://")):
        match = _WEIBO_URL_RE.search(target)
        if not match:
            raise ValueError(f"无法识别微博用户：{target}")
        target = match.group("url").rstrip(_URL_TRAILING_PUNCTUATION)
    parsed = urlparse(target)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"weibo.com", "www.weibo.com", "m.weibo.cn"}:
        raise ValueError(f"不是受支持的微博地址：{target}")

    query = parse_qs(parsed.query)
    for key in ("uid", "user_id"):
        candidate = (query.get(key) or [""])[0]
        if candidate.isdecimal():
            return candidate

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 2 and segments[0].lower() in {"u", "profile"}:
        if segments[1].isdecimal():
            return segments[1]
    if hostname in {"weibo.com", "www.weibo.com"} and segments:
        if segments[0].isdecimal():
            return segments[0]
    raise ValueError(
        "链接中没有微博 UID；请粘贴用户主页，或直接输入数字 UID"
    )


def configure_utf8_console() -> None:
    """Prevent Chinese logs from failing on Windows GBK consoles."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def activate_vendor() -> None:
    if not VENDOR_ROOT.is_dir():
        raise RuntimeError(f"Vendored weibo-crawler not found: {VENDOR_ROOT}")
    vendor_path = str(VENDOR_ROOT)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)


def ensure_config(config_path: Path) -> Path:
    """Create the ignored default config from the tracked example."""
    config_path = config_path.expanduser().resolve()
    if config_path.exists():
        return config_path
    if config_path != DEFAULT_CONFIG_PATH.resolve():
        raise FileNotFoundError(f"Weibo config not found: {config_path}")
    if not EXAMPLE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Weibo config template not found: {EXAMPLE_CONFIG_PATH}"
        )
    shutil.copyfile(EXAMPLE_CONFIG_PATH, config_path)
    return config_path


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load the JSON/JSON5 config used by upstream weibo-crawler."""
    import json5

    try:
        config = json5.loads(config_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError(f"无法读取微博配置 {config_path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"微博配置必须是 JSON 对象: {config_path}")
    return config


def _absolute_config_path(value: str, config_directory: Path) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config_directory / path
    return str(path.resolve())


def normalize_config(
    config: Dict[str, Any], config_path: Path
) -> Dict[str, Any]:
    """Resolve project-side paths without modifying vendored source."""
    normalized = copy.deepcopy(config)
    config_directory = config_path.expanduser().resolve().parent

    user_id_list = normalized.get("user_id_list")
    if isinstance(user_id_list, list):
        normalized["user_id_list"] = [
            extract_weibo_user_id(user_id) for user_id in user_id_list
        ]
    elif isinstance(user_id_list, str) and user_id_list:
        if user_id_list.lower().endswith(".txt"):
            normalized["user_id_list"] = _absolute_config_path(
                user_id_list, config_directory
            )
        else:
            normalized["user_id_list"] = [extract_weibo_user_id(user_id_list)]

    cookie = normalized.get("cookie")
    if isinstance(cookie, str) and cookie.lower().endswith(".txt"):
        normalized["cookie"] = _absolute_config_path(cookie, config_directory)

    sqlite_path = normalized.get("sqlite_db_path")
    if isinstance(sqlite_path, str) and sqlite_path:
        normalized["sqlite_db_path"] = _absolute_config_path(
            sqlite_path, config_directory
        )

    output_directory = normalized.get("output_directory", "download_files/weibo")
    output_path = Path(str(output_directory)).expanduser()
    if not output_path.is_absolute():
        output_path = config_directory / output_path
    # Upstream concatenates its source directory with output_directory instead
    # of using an absolute-path-aware join.  A relative path from the vendor
    # directory keeps all generated media in the project-selected directory.
    normalized["output_directory"] = os.path.relpath(
        output_path.resolve(), VENDOR_ROOT.resolve()
    )
    return normalized


def apply_overrides(
    config: Dict[str, Any], arguments: argparse.Namespace
) -> Dict[str, Any]:
    overridden = copy.deepcopy(config)
    if arguments.user_ids:
        overridden["user_id_list"] = [
            extract_weibo_user_id(user_id)
            for user_id in arguments.user_ids
            if user_id.strip()
        ]
    if arguments.since_date is not None:
        overridden["since_date"] = _date_or_days(arguments.since_date)
    if arguments.end_date is not None:
        overridden["end_date"] = _date_or_days(arguments.end_date)
    if arguments.only_original is not None:
        overridden["only_crawl_original"] = int(arguments.only_original)
    return overridden


def _date_or_days(value: str) -> Any:
    stripped = value.strip()
    return int(stripped) if stripped.isdecimal() else stripped


def has_crawl_targets(config: Dict[str, Any]) -> bool:
    user_id_list = config.get("user_id_list")
    if isinstance(user_id_list, list):
        return any(str(user_id).strip() for user_id in user_id_list)
    return isinstance(user_id_list, str) and bool(user_id_list.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "使用 vendored dataabc/weibo-crawler 按微博用户 ID 下载图片、"
            "视频和 Live Photo。"
        )
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"JSON/JSON5 配置文件（默认：{DEFAULT_CONFIG_PATH.name}）",
    )
    parser.add_argument(
        "-u",
        "--user-id",
        dest="user_ids",
        action="append",
        help="微博 UID、用户主页或带 UID 的链接；可重复传入",
    )
    parser.add_argument(
        "--since-date",
        help="起始日期（YYYY-MM-DD）或最近天数（整数）",
    )
    parser.add_argument(
        "--end-date",
        help="截止日期（YYYY-MM-DD/完整时间）或距今天数",
    )
    original_group = parser.add_mutually_exclusive_group()
    original_group.add_argument(
        "--only-original",
        dest="only_original",
        action="store_true",
        default=None,
        help="只抓取原创微博",
    )
    original_group.add_argument(
        "--include-retweets",
        dest="only_original",
        action="store_false",
        help="同时抓取转发微博",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="启动上游 Flask API 服务，而不是立即抓取",
    )
    parser.add_argument("--host", default="127.0.0.1", help="API 监听地址")
    parser.add_argument("--port", type=int, default=5000, help="API 监听端口")
    parser.add_argument(
        "--scheduled-refresh",
        action="store_true",
        help="API 模式下同时启动上游每 10 分钟刷新任务",
    )
    return parser


def run_crawler(config: Dict[str, Any]) -> int:
    previous_cwd = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        sqlite_path = config.get("sqlite_db_path")
        if isinstance(sqlite_path, str) and sqlite_path:
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

        activate_vendor()
        from weibo import Weibo

        Weibo(config).start()
    finally:
        os.chdir(previous_cwd)
    return 0


def run_service(
    config: Dict[str, Any],
    host: str,
    port: int,
    scheduled_refresh: bool,
) -> int:
    previous_cwd = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        activate_vendor()
        upstream_weibo = importlib.import_module("weibo")
        upstream_weibo.get_config = lambda: copy.deepcopy(config)
        service = importlib.import_module("service")
        service.base_config = copy.deepcopy(config)
        service.DATABASE_PATH = config.get("sqlite_db_path", "weibodata.db")

        if scheduled_refresh:
            threading.Thread(
                target=service.schedule_refresh,
                daemon=True,
                name="weibo-crawler-scheduler",
            ).start()

        service.app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
        )
    finally:
        os.chdir(previous_cwd)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_utf8_console()
    parser = build_parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        config_path = ensure_config(arguments.config)
        config = load_config(config_path)
        config = apply_overrides(config, arguments)
        config = normalize_config(config, config_path)
    except (FileNotFoundError, ValueError) as error:
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 2

    if arguments.serve:
        return run_service(
            config,
            host=arguments.host,
            port=arguments.port,
            scheduled_refresh=arguments.scheduled_refresh,
        )
    if not has_crawl_targets(config):
        parser.print_usage(sys.stderr)
        print(
            f"{parser.prog}: error: 请通过 -u/--user-id 或 "
            f"{config_path.name} 的 user_id_list 指定至少一个微博用户 ID",
            file=sys.stderr,
        )
        return 2
    return run_crawler(config)


if __name__ == "__main__":
    raise SystemExit(main())
