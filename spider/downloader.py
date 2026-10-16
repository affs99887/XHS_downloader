"""Unified interactive entry point for Xiaohongshu, Douyin and Weibo."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_utf8_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("XHS_QR_FULL_BLOCK", "1")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def run_module(module: str, arguments: Sequence[str]) -> int:
    command = [sys.executable, "-m", module, *arguments]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


def run_xhs(arguments: argparse.Namespace) -> int:
    forwarded = []
    if arguments.likes:
        forwarded.append("--likes")
    elif arguments.target:
        forwarded.append(arguments.target)
    else:
        raise ValueError("请提供小红书笔记链接，或使用 --likes")
    if arguments.limit:
        forwarded.extend(["--limit", str(arguments.limit)])
    if arguments.output:
        forwarded.extend(["--output", arguments.output])
    return run_module("spider.xhs_downloader", forwarded)


def run_douyin(arguments: argparse.Namespace) -> int:
    if arguments.login:
        return run_module("spider.douyin_downloader", ["login"])
    if not arguments.target:
        raise ValueError("请提供抖音链接或完整分享口令")
    return run_module("spider.douyin_downloader", ["-u", arguments.target])


def save_weibo_cookie(cookie: str) -> Path:
    cookie = cookie.strip()
    if not cookie:
        raise ValueError("Cookie 不能为空")
    from spider.weibo_downloader import ensure_config, load_config

    config_path = ensure_config(PROJECT_ROOT / "weibo_config.json")
    cookie_path = PROJECT_ROOT / "weibo_cookie.txt"
    cookie_path.write_text(cookie, encoding="utf-8")
    config = load_config(config_path)
    config["cookie"] = cookie_path.name
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return cookie_path


def run_weibo(arguments: argparse.Namespace) -> int:
    if arguments.set_cookie:
        cookie = getpass.getpass("粘贴微博网页 Cookie（输入不会显示）：").strip()
        cookie_path = save_weibo_cookie(cookie)
        print(f"微博 Cookie 已保存到：{cookie_path}")
        return 0
    if not arguments.targets:
        raise ValueError("请提供微博 UID、用户主页或带 UID 的微博链接")
    forwarded = []
    for target in arguments.targets:
        forwarded.extend(["-u", target])
    if arguments.since_date:
        forwarded.extend(["--since-date", arguments.since_date])
    if arguments.only_original:
        forwarded.append("--only-original")
    return run_module("spider.weibo_downloader", forwarded)


def _wait_for_menu() -> None:
    try:
        input("\n按回车键返回主菜单……")
    except EOFError:
        pass


def _prompt(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("输入不能为空。")


def interactive_menu() -> int:
    while True:
        print("\n==============================")
        print(" 小红书 / 抖音 / 微博统一下载器")
        print("==============================")
        print("1. 小红书")
        print("2. 抖音")
        print("3. 微博")
        print("0. 退出")
        choice = input("\n请选择平台：").strip()

        if choice == "0":
            return 0
        if choice == "1":
            print("\n1. 粘贴笔记链接或分享文字")
            print("2. 下载当前账号的喜欢列表")
            mode = input("请选择：").strip()
            if mode == "1":
                target = _prompt("粘贴小红书内容：")
                code = run_module("spider.xhs_downloader", [target])
            elif mode == "2":
                limit = input("最多下载多少条（直接回车=全部）：").strip()
                forwarded = ["--likes"]
                if limit:
                    forwarded.extend(["--limit", limit])
                code = run_module("spider.xhs_downloader", forwarded)
            else:
                print("无效选择。")
                continue
        elif choice == "2":
            print("\n1. 粘贴作品、图集或主页分享文字")
            print("2. 登录或更新抖音 Cookie")
            mode = input("请选择：").strip()
            if mode == "1":
                target = _prompt("粘贴抖音内容：")
                code = run_module("spider.douyin_downloader", ["-u", target])
            elif mode == "2":
                code = run_module("spider.douyin_downloader", ["login"])
            else:
                print("无效选择。")
                continue
        elif choice == "3":
            print("\n1. 下载指定用户的微博媒体")
            print("2. 设置或更新微博 Cookie")
            mode = input("请选择：").strip()
            if mode == "1":
                target = _prompt("粘贴微博 UID、用户主页或带 UID 的微博链接：")
                days = input("下载最近多少天（直接回车=30）：").strip()
                forwarded = ["-u", target]
                if days:
                    forwarded.extend(["--since-date", days])
                code = run_module("spider.weibo_downloader", forwarded)
            elif mode == "2":
                cookie = getpass.getpass("粘贴微博网页 Cookie（输入不会显示）：").strip()
                if not cookie:
                    print("Cookie 不能为空。")
                    continue
                cookie_path = save_weibo_cookie(cookie)
                print(f"微博 Cookie 已保存到：{cookie_path}")
                code = 0
            else:
                print("无效选择。")
                continue
        else:
            print("无效选择。")
            continue

        print("\n下载完成。" if code == 0 else f"\n执行失败，退出码：{code}")
        _wait_for_menu()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="小红书、抖音、微博统一下载入口；不带参数时打开交互菜单"
    )
    subparsers = parser.add_subparsers(dest="platform")

    xhs = subparsers.add_parser("xhs", help="小红书下载")
    xhs.add_argument("target", nargs="?", help="笔记链接或分享文字")
    xhs.add_argument("--likes", action="store_true", help="下载当前账号的喜欢列表")
    xhs.add_argument("--limit", type=int, default=0, help="喜欢列表最多处理几条")
    xhs.add_argument("--output", default="", help="自定义输出目录")

    douyin = subparsers.add_parser("douyin", help="抖音下载")
    douyin.add_argument("target", nargs="?", help="链接或分享口令")
    douyin.add_argument("--login", action="store_true", help="登录或更新 Cookie")

    weibo = subparsers.add_parser("weibo", help="微博下载")
    weibo.add_argument("targets", nargs="*", help="UID、用户主页或带 UID 的链接")
    weibo.add_argument(
        "--since-date",
        "--days",
        dest="since_date",
        help="开始日期或最近天数",
    )
    weibo.add_argument("--only-original", action="store_true", help="只下载原创微博")
    weibo.add_argument(
        "--set-cookie",
        action="store_true",
        help="安全提示并保存微博 Cookie",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_utf8_console()
    parser = build_parser()
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not arguments.platform:
        try:
            return interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            return 130

    try:
        if arguments.platform == "xhs":
            return run_xhs(arguments)
        if arguments.platform == "douyin":
            return run_douyin(arguments)
        if arguments.platform == "weibo":
            return run_weibo(arguments)
    except ValueError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
