"""Persistent batch reports and opt-in retries shared by the downloaders."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def add_batch_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("批次日志、重试和图片筛选")
    group.add_argument("--no-retry", action="store_true", help="结束时不询问重试；仍保存失败清单")
    group.add_argument("--retry-failed", type=Path, help="只重试指定 failed_downloads.json 中的失败项")
    group.add_argument("--image-filter", choices=("legs", "stockings", "person", "off"), default="legs",
                       help="图片筛选：legs=人物且有可见腿部（默认），stockings=黑丝袜（实验），person=人物，off=关闭")
    group.add_argument("--log-dir", type=Path, default=PROJECT_ROOT / "log", help="批次日志总目录")


def batch_option_arguments(arguments) -> list[str]:
    result = []
    if getattr(arguments, "no_retry", False):
        result.append("--no-retry")
    for name in ("retry_failed", "log_dir"):
        value = getattr(arguments, name, None)
        if value is not None:
            result.extend(["--" + name.replace("_", "-"), str(value)])
    mode = getattr(arguments, "image_filter", "legs")
    if mode != "legs":
        result.extend(["--image-filter", mode])
    return result


def read_failure_tasks(path: Path, platform: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("platform") != platform:
        raise ValueError(f"失败清单不属于 {platform}: {path}")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
        raise ValueError(f"失败清单格式无效: {path}")
    return tasks


class DownloadBatch:
    def __init__(self, platform: str, *, log_dir: Path | None = None,
                 no_retry: bool = False, image_filter: str = "legs"):
        self.platform = platform
        self.no_retry = no_retry
        self.image_filter = image_filter
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + uuid4().hex[:8]
        self.directory = Path(log_dir or PROJECT_ROOT / "log").expanduser().resolve() / platform / run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.failure_file = self.directory / "failed_downloads.json"
        self.failures: dict[str, dict] = {}
        self.retries: dict[str, Callable] = {}
        self.images: dict[Path, Path] = {}
        self.attempts: dict[str, int] = {}
        self.successes: set[str] = set()
        self.sort_counts: dict[str, int] = {}
        self._sink = None
        self._handler = None
        self._loggers = []
        self._finished = False
        self._write_failures()

    @classmethod
    def from_arguments(cls, platform, arguments):
        return cls(platform, log_dir=arguments.log_dir, no_retry=arguments.no_retry,
                   image_filter=arguments.image_filter)

    def __enter__(self):
        self._sink = logger.add(str(self.directory / "run.log"), encoding="utf-8",
                                level="INFO", backtrace=False, diagnose=False)
        self._handler = logging.FileHandler(self.directory / "run.log", encoding="utf-8")
        self._handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        self.capture_loggers()
        logger.info(f"本次日志：{self.directory}")
        self.event("batch_started", platform=self.platform, image_filter=self.image_filter)
        return self

    def capture_loggers(self):
        """Include vendor loggers which deliberately disable propagation."""
        if self._handler is None:
            return
        candidates = [logging.getLogger(), *list(logging.Logger.manager.loggerDict.values())]
        for candidate in candidates:
            if isinstance(candidate, logging.Logger) and (candidate is logging.getLogger() or not candidate.propagate):
                if candidate not in self._loggers:
                    candidate.addHandler(self._handler)
                    self._loggers.append(candidate)

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc is not None:
                self.event("batch_interrupted", error=str(exc))
            self._write_summary(completed=self._finished and exc is None)
        finally:
            for candidate in self._loggers:
                candidate.removeHandler(self._handler)
            if self._handler:
                self._handler.close()
            if self._sink is not None:
                logger.remove(self._sink)

    def event(self, status: str, **values) -> None:
        record = {"time": datetime.now().isoformat(timespec="seconds"), "status": status, **values}
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write_json(self, path: Path, value) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _write_failures(self) -> None:
        self._write_json(self.failure_file, {"version": 1, "platform": self.platform,
                                           "tasks": list(self.failures.values())})

    def failed(self, key: str, label: str, payload: dict, error, retry: Callable | None = None) -> None:
        self.attempts[key] = self.attempts.get(key, 0) + 1
        self.successes.discard(key)
        self.failures[key] = {"key": key, "label": label, "payload": payload,
                              "error": str(error), "attempts": self.attempts[key]}
        if retry is not None:
            self.retries[key] = retry
        self._write_failures()
        self.event("failed", **self.failures[key])
        logger.error(f"失败：{label}；{error}")

    def succeeded(self, key: str, label: str = "") -> None:
        self.attempts[key] = self.attempts.get(key, 0) + 1
        self.successes.add(key)
        if key in self.failures:
            del self.failures[key]
            self._write_failures()
        self.retries.pop(key, None)
        self.event("succeeded", key=key, label=label)

    def attempt(self, key: str, label: str, payload: dict, action: Callable):
        def execute():
            return self.attempt(key, label, payload, action)
        try:
            value = action()
        except Exception as error:
            self.failed(key, label, payload, error, execute)
            return None
        self.succeeded(key, label)
        return value

    def add_image(self, path, root) -> None:
        path, root = Path(path).resolve(), Path(root).resolve()
        if path.is_relative_to(root) and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            self.images[path] = root

    def retry_failures(self) -> None:
        while self.failures:
            logger.warning(f"本轮结束，尚有 {len(self.failures)} 项失败；清单：{self.failure_file}")
            keys = [key for key in self.failures if key in self.retries]
            if self.no_retry or not keys or not sys.stdin.isatty():
                break
            try:
                answer = input(f"是否重试这 {len(keys)} 个失败项？[y/N]：").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已保留失败清单。")
                break
            if answer not in {"y", "yes", "是", "重试"}:
                break
            self.event("retry_round", count=len(keys))
            for key in keys:
                # An earlier retry can also resolve a related task.
                callback = self.retries.get(key)
                task = self.failures.get(key)
                if callback is None or task is None:
                    continue
                try:
                    callback()
                except Exception as error:
                    self.failed(key, task["label"], task["payload"], error, callback)

    def finish(self, *, dry_run=False, preview=False) -> int:
        self.retry_failures()
        if self.images and not dry_run and self.image_filter != "off":
            from spider.image_filter import sort_images
            self.sort_counts = sort_images(self.images, self.directory, mode=self.image_filter, preview=preview)
        self._finished = True
        self._write_summary(completed=True)
        logger.info(f"批次结束：成功 {len(self.successes)} 项，失败 {len(self.failures)} 项；日志：{self.directory}")
        return int(bool(self.failures) or bool(self.sort_counts.get("errors")))

    def _write_summary(self, *, completed) -> None:
        self._write_json(self.directory / "summary.json", {
            "platform": self.platform, "completed": completed,
            "successful_tasks": len(self.successes), "failed_tasks": len(self.failures),
            "image_filter": self.image_filter, "images": self.sort_counts,
            "failure_file": str(self.failure_file),
        })
