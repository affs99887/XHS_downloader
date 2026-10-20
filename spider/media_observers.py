"""Observe vendored downloaders without changing their source code."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import copy
import logging
from pathlib import Path

from spider.image_filter import IMAGE_SUFFIXES, sorted_media_exists


@contextmanager
def replace_attribute(owner, name, value):
    original = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield original
    finally:
        setattr(owner, name, original)


def saved_weibo_file(path: Path) -> Path | None:
    for candidate in [path, *(path.with_suffix(suffix) for suffix in
                             (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".webm"))]:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


@contextmanager
def observe_weibo(crawler_class, batch, output_root):
    from contextlib import ExitStack

    original = crawler_class.download_one_file
    original_pages = crawler_class.get_pages

    class PageErrors(logging.Handler):
        def __init__(self):
            super().__init__()
            self.errors = []

        def emit(self, record):
            if record.funcName in {"get_pages", "get_one_page", "get_json"} and record.exc_info:
                self.errors.append(record.getMessage())

    def pages(instance):
        user_config = copy.deepcopy(instance.user_config)
        query = getattr(instance, "query", "")
        user_id = str(user_config.get("user_id", "unknown"))
        key = f"weibo_user:{user_id}:{query}"
        payload = {"kind": "weibo_user", "user_config": user_config, "query": query,
                   "output_root": str(output_root)}

        def retry():
            instance.initialize_info(copy.deepcopy(user_config))
            instance.query = query
            context = (nullcontext() if crawler_class.download_one_file is observed
                       else replace_attribute(crawler_class, "download_one_file", observed))
            with context:
                pages(instance)

        errors = PageErrors()
        vendor_logger = logging.getLogger("weibo")
        vendor_logger.addHandler(errors)
        try:
            try:
                original_pages(instance)
            except SystemExit as error:
                raise RuntimeError(f"微博用户抓取提前退出：{error.code}") from error
            if not instance.user:
                raise RuntimeError("无法获取微博用户信息，请检查 UID 或登录状态")
            if errors.errors:
                raise RuntimeError("；".join(errors.errors))
            batch.succeeded(key, f"微博用户 {user_id}")
        except Exception as error:
            batch.failed(key, f"微博用户 {user_id}", payload, error, retry)
        finally:
            vendor_logger.removeHandler(errors)

    def observed(instance, url, file_path, media_type, weibo_id, created_at):
        path = Path(file_path).resolve()
        key = f"weibo_media:{path}"
        payload = {"kind": "weibo_media", "url": url, "file_path": str(path),
                   "media_type": media_type, "weibo_id": str(weibo_id), "created_at": created_at,
                   "output_root": str(output_root)}

        def retry():
            return observed(instance, url, str(path), media_type, weibo_id, created_at)

        try:
            if not sorted_media_exists(path, Path(output_root)):
                original(instance, url, str(path), media_type, weibo_id, created_at)
            saved = saved_weibo_file(path)
            if saved is None and not sorted_media_exists(path, Path(output_root)):
                raise RuntimeError("上游下载失败，未生成完整媒体；详情见 run.log")
            batch.succeeded(key, str(path))
            if saved and saved.suffix.lower() in IMAGE_SUFFIXES:
                batch.add_image(saved, output_root)
        except Exception as error:
            batch.failed(key, str(path), payload, error, retry)

    with ExitStack() as stack:
        stack.enter_context(replace_attribute(crawler_class, "download_one_file", observed))
        stack.enter_context(replace_attribute(crawler_class, "get_pages", pages))
        yield


def douyin_retry_arguments(arguments, url):
    result = []
    index = 0
    while index < len(arguments):
        value = arguments[index]
        if value in {"-u", "--url"}:
            index += 2
            continue
        if not value.startswith("--url="):
            result.append(value)
        index += 1
    return [*result, "-u", url]


@contextmanager
def observe_douyin(batch, arguments, invoke, force_ids=None):
    from contextlib import ExitStack
    from cli import main as cli
    from core.downloader_base import BaseDownloader
    from storage.file_manager import FileManager

    force_ids = force_ids if force_ids is not None else set()
    original_progress = BaseDownloader._progress_advance_item
    original_should = BaseDownloader._should_download
    original_persist = FileManager._persist_stream
    original_file = FileManager.download_file
    original_assets = BaseDownloader._download_aweme_assets
    original_url = cli.download_url

    def retry_url(url, key):
        def retry():
            invoke(douyin_retry_arguments(arguments, url))
            # The observers update this key during the fresh invocation.
        return retry

    def progress(instance, status, detail=""):
        original_progress(instance, status, detail)
        if not str(detail).isdecimal():
            return
        aweme_id = str(detail)
        key = f"douyin_aweme:{aweme_id}"
        url = f"https://www.douyin.com/video/{aweme_id}"
        payload = {"kind": "douyin_url", "url": url,
                   "arguments": douyin_retry_arguments(arguments, url), "aweme_id": aweme_id}
        if status == "failed":
            force_ids.add(aweme_id)
            batch.failed(key, url, payload, "作品下载失败；详情见 run.log", retry_url(url, key))
        elif status in {"success", "skipped"}:
            force_ids.discard(aweme_id)
            batch.succeeded(key, url)

    async def should_download(instance, aweme_id):
        if str(aweme_id) in force_ids:
            return True
        return await original_should(instance, aweme_id)

    async def persist(instance, chunk_iter, save_path, *args, **kwargs):
        result = await original_persist(instance, chunk_iter, save_path, *args, **kwargs)
        if result:
            actual_path = result if isinstance(result, Path) else instance._resolve_save_path_from_content_type(
                save_path, args[1] if len(args) > 1 else kwargs.get("response_headers"),
                prefer_response_content_type=kwargs.get("prefer_response_content_type", False))
            batch.add_image(actual_path, instance.base_path)
            batch.event("media_downloaded", path=str(actual_path))
        return result

    async def download_file(instance, url, save_path, *args, **kwargs):
        candidates = [Path(save_path)]
        if kwargs.get("prefer_response_content_type") and Path(save_path).suffix.lower() in IMAGE_SUFFIXES:
            candidates.extend(Path(save_path).with_suffix(suffix) for suffix in sorted(IMAGE_SUFFIXES))
        for candidate in candidates:
            if candidate.is_file() and candidate.stat().st_size > 0:
                batch.add_image(candidate, instance.base_path)
                batch.event("media_skipped", path=str(candidate))
                return candidate if kwargs.get("return_saved_path") else True
            try:
                relative = candidate.resolve().relative_to(Path(instance.base_path).resolve())
            except ValueError:
                continue
            for folder in ("弃用", "待复核"):
                classified = Path(instance.base_path) / folder / relative
                if classified.is_file() and classified.stat().st_size > 0:
                    return classified if kwargs.get("return_saved_path") else True
        result = await original_file(instance, url, save_path, *args, **kwargs)
        if not result:
            batch.event("media_attempt_failed", path=str(save_path), url=url)
        return result

    async def assets(instance, aweme_data, *args, **kwargs):
        try:
            return await original_assets(instance, aweme_data, *args, **kwargs)
        except Exception as error:
            aweme_id = str(aweme_data.get("aweme_id") or "")
            if aweme_id:
                force_ids.add(aweme_id)
                key = f"douyin_aweme:{aweme_id}"
                url = f"https://www.douyin.com/video/{aweme_id}"
                payload = {"kind": "douyin_url", "url": url, "aweme_id": aweme_id,
                           "arguments": douyin_retry_arguments(arguments, url)}
                batch.failed(key, url, payload, error, retry_url(url, key))
            raise

    async def download_url(url, *args, **kwargs):
        key = f"douyin_url:{url}"
        before = batch.attempts.copy()
        payload = {"kind": "douyin_url", "url": url,
                   "arguments": douyin_retry_arguments(arguments, url)}
        try:
            result = await original_url(url, *args, **kwargs)
        except Exception as error:
            batch.failed(key, url, payload, error, retry_url(url, key))
            raise
        reported_failures = [item for item in batch.failures if item.startswith("douyin_aweme:")
                             and batch.attempts[item] > before.get(item, 0)]
        if result is None or getattr(result, "failed", 0) > len(reported_failures):
            batch.failed(key, url, payload, "链接获取或部分作品下载失败；详情见 run.log", retry_url(url, key))
        else:
            batch.succeeded(key, url)
        return result

    with ExitStack() as stack:
        stack.enter_context(replace_attribute(BaseDownloader, "_progress_advance_item", progress))
        stack.enter_context(replace_attribute(BaseDownloader, "_should_download", should_download))
        stack.enter_context(replace_attribute(FileManager, "_persist_stream", persist))
        stack.enter_context(replace_attribute(FileManager, "download_file", download_file))
        stack.enter_context(replace_attribute(BaseDownloader, "_download_aweme_assets", assets))
        stack.enter_context(replace_attribute(cli, "download_url", download_url))
        batch.capture_loggers()
        file_logger = logging.getLogger("FileManager")
        previous_level = file_logger.level
        file_logger.setLevel(logging.DEBUG)
        try:
            yield
        finally:
            file_logger.setLevel(previous_level)
