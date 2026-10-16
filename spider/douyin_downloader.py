"""Project entry point for the vendored douyin-downloader.

The upstream project intentionally uses top-level package names such as
``core`` and ``config``.  Keeping it under ``vendor/douyin_downloader`` avoids
mixing those modules with the Xiaohongshu implementation.  This wrapper adds
the vendor directory to ``sys.path`` only while the Douyin command is running.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "douyin_downloader"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "douyin_config.yml"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "douyin_config.example.yml"
DEFAULT_COOKIE_PATH = PROJECT_ROOT / "douyin_cookies.json"

_DOUYIN_URL_RE = re.compile(
    r"(?P<url>(?:https?://)?(?:"
    r"v\.douyin\.com|v\.iesdouyin\.com|www\.douyin\.com|"
    r"www\.iesdouyin\.com|live\.douyin\.com|webcast\.amemv\.com"
    r")/[^\s]+)",
    re.IGNORECASE,
)
_URL_TRAILING_PUNCTUATION = "，。；;！!）》】]}>'\""


def extract_douyin_url(value: str) -> str:
    """Extract the first supported URL from a Douyin share message."""
    match = _DOUYIN_URL_RE.search(value.strip())
    if not match:
        return value.strip()
    return match.group("url").rstrip(_URL_TRAILING_PUNCTUATION)


def normalize_url_arguments(arguments: Sequence[str]) -> List[str]:
    """Normalize ``-u/--url`` values while preserving all other arguments."""
    normalized: List[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in {"-u", "--url"} and index + 1 < len(arguments):
            normalized.extend([argument, extract_douyin_url(arguments[index + 1])])
            index += 2
            continue
        if argument.startswith("--url="):
            normalized.append("--url=" + extract_douyin_url(argument.split("=", 1)[1]))
        else:
            normalized.append(argument)
        index += 1
    return normalized


def has_option(arguments: Sequence[str], *names: str) -> bool:
    for argument in arguments:
        if argument in names:
            return True
        if any(argument.startswith(name + "=") for name in names if name.startswith("--")):
            return True
    return False


def ensure_default_config() -> Path:
    """Create the ignored runtime config from the tracked example on first use."""
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if not EXAMPLE_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Douyin config template not found: {EXAMPLE_CONFIG_PATH}")
    shutil.copyfile(EXAMPLE_CONFIG_PATH, DEFAULT_CONFIG_PATH)
    return DEFAULT_CONFIG_PATH


def activate_vendor() -> None:
    if not VENDOR_ROOT.is_dir():
        raise RuntimeError(f"Vendored douyin-downloader not found: {VENDOR_ROOT}")
    vendor_path = str(VENDOR_ROOT)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)


def configure_utf8_console() -> None:
    """Prevent Rich symbols and Chinese text from failing on Windows GBK."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _run_downloader(arguments: Sequence[str]) -> int:
    configure_utf8_console()
    activate_vendor()
    from cli.main import main as upstream_main

    config_path = ensure_default_config()
    forwarded = normalize_url_arguments(arguments)
    if not has_option(forwarded, "-c", "--config"):
        forwarded = ["--config", str(config_path), *forwarded]

    previous_argv = sys.argv[:]
    previous_cwd = Path.cwd()
    sys.argv = [str(VENDOR_ROOT / "run.py"), *forwarded]
    os.chdir(PROJECT_ROOT)
    try:
        upstream_main()
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)
    return 0


def _run_login(arguments: Sequence[str]) -> int:
    configure_utf8_console()
    activate_vendor()
    from tools.cookie_fetcher import main as login_main

    config_path = ensure_default_config()
    forwarded = list(arguments)
    if not has_option(forwarded, "--config"):
        forwarded = ["--config", str(config_path), *forwarded]
    if not has_option(forwarded, "--output"):
        forwarded = ["--output", str(DEFAULT_COOKIE_PATH), *forwarded]

    previous_cwd = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        return int(login_main(forwarded) or 0)
    finally:
        os.chdir(previous_cwd)


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0].lower() == "login":
        return _run_login(arguments[1:])
    return _run_downloader(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
