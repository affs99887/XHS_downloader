import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from spider.spider import Data_Spider
from xhs_utils.common_util import load_or_login_cookies
from xhs_utils.data_util import check_and_create_path, download_media, norm_str
from spider.download_batch import DownloadBatch, add_batch_options, read_failure_tasks
from spider.image_filter import sorted_media_exists


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Download media from notes liked by the logged-in account.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum liked notes to process. 0 means all.")
    parser.add_argument("--output", default="", help="Base output directory. Defaults to download_files/likes.")
    parser.add_argument("--run-dir", default="", help="Current run media directory. Defaults to output/current timestamp.")
    parser.add_argument("--record-file", default="", help="Downloaded note record file. Defaults to output/downloaded_notes.jsonl.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between note detail requests, in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch note details and print counts without downloading.")
    parser.add_argument("--compressed-images", action="store_true", help="Download CDN preview images instead of original JPEGs.")
    parser.add_argument("--overwrite-images", action="store_true", help="Replace existing image files. Existing videos are still skipped.")
    parser.add_argument(
        "--continue-past-downloaded",
        action="store_true",
        help="Continue after a downloaded note is found. By default the downloader stops for incremental runs.",
    )
    add_batch_options(parser)
    return parser.parse_args(argv)


def get_current_user_id(api, cookies_str):
    success, msg, res = api.get_user_self_info2(cookies_str)
    if not success:
        raise RuntimeError(f"获取当前账号信息失败: {msg}")
    user_id = res.get("data", {}).get("user_id")
    if not user_id:
        raise RuntimeError("当前账号信息中没有 user_id")
    return user_id


def iter_liked_notes(api, user_id, cookies_str, limit=0):
    cursor = ""
    seen = 0
    while True:
        success, msg, res = api.get_user_like_note_info(user_id, cursor, cookies_str)
        if not success:
            raise RuntimeError(f"获取喜欢列表失败: {msg}")

        data = res.get("data") or {}
        notes = data.get("notes") or []
        if not notes:
            break

        for note in notes:
            yield note
            seen += 1
            if limit and seen >= limit:
                return

        if not data.get("has_more"):
            break
        next_cursor = str(data.get("cursor", ""))
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor


def liked_note_url(note):
    note_id = note.get("note_id") or note.get("id")
    xsec_token = note.get("xsec_token", "")
    if not note_id:
        return ""
    return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_user"


def original_image_url(url):
    success, msg, converted_url = XHS_Apis.get_note_no_water_img(url)
    if success and converted_url:
        return converted_url
    logger.info(f"无法获取原图地址，将尝试下载预览图: {msg}")
    return url


def media_items_from_note(note_info, use_original_images=True):
    items = []
    seen = set()
    is_video_note = note_info.get("note_type") == "视频"
    if not is_video_note:
        for index, url in enumerate(note_info.get("image_list") or []):
            if url and url not in seen:
                fallback_url = url
                if use_original_images:
                    url = original_image_url(url)
                items.append((f"image_{index:02d}", url, "image", fallback_url))
                seen.add(fallback_url)
    video = note_info.get("video_addr")
    if video and video not in seen:
        items.append(("video", video, "video", None))
    return items


def media_file_stem(note_info, label):
    note_id = norm_str(note_info.get("note_id") or "unknown")
    title = norm_str(note_info.get("title") or "untitled")[:32] or "untitled"
    return f"{note_id}_{label}_{title}"


def download_media_with_fallback(path, name, url, media_type, fallback_url=None):
    try:
        download_media(path, name, url, media_type)
    except Exception as original_error:
        if media_type == "image" and fallback_url and fallback_url != url:
            try:
                download_media(path, name, fallback_url, media_type)
            except Exception as preview_error:
                raise RuntimeError(f"原图和预览图均下载失败；原图：{original_error}；预览图：{preview_error}") from preview_error
            logger.info(f"下载原图失败，预览图下载成功：{name}")
            return False
        raise
    if media_type == "image":
        is_original = not fallback_url or fallback_url != url
        logger.info(f"{'原图' if is_original else '预览图'}下载成功：{name}")
        return is_original
    logger.info(f"视频下载成功：{name}")
    return True


class MediaDownloadError(RuntimeError):
    def __init__(self, failures):
        self.failed_paths = set(failures)
        super().__init__(f"{len(failures)} 个媒体失败：" + "；".join(f"{path.name}: {error}" for path, error in failures.items()))


def save_note_media(note_info, output_root, dry_run=False, use_original_images=True, overwrite_images=False,
                    batch=None, retry_paths=None):
    media_items = media_items_from_note(note_info, use_original_images)
    if dry_run:
        return len(media_items), 0, 0, 0
    if not media_items:
        raise RuntimeError("笔记未返回有效的媒体地址")

    check_and_create_path(output_root)
    downloaded = 0
    original_count = 0
    fallback_count = 0
    failures = {}
    for label, url, media_type, fallback_url in media_items:
        name = media_file_stem(note_info, label)
        suffix = "jpg" if media_type == "image" else "mp4"
        file_path = Path(output_root) / f"{name}.{suffix}"
        if sorted_media_exists(file_path, Path(output_root)):
            force_retry = retry_paths and file_path in retry_paths
            if not force_retry and (media_type != "image" or not overwrite_images):
                logger.info(f"已存在，跳过: {file_path}")
                if batch is not None and media_type == "image" and file_path.is_file():
                    batch.add_image(file_path, output_root)
                continue
        try:
            used_primary = download_media_with_fallback(output_root, name, url, media_type, fallback_url)
        except Exception as error:
            failures[file_path] = error
            logger.error(f"媒体下载失败，继续本条剩余媒体：{file_path.name}；{error}")
            if batch is not None:
                batch.event("media_failed", note_id=note_info.get("note_id"), path=str(file_path), error=str(error))
            continue
        if media_type == "image":
            if used_primary and use_original_images and url != fallback_url:
                original_count += 1
            else:
                fallback_count += 1
        downloaded += 1
        if batch is not None:
            batch.event("media_downloaded", path=str(file_path), media_type=media_type, original=used_primary)
            if media_type == "image":
                batch.add_image(file_path, output_root)
    if failures:
        raise MediaDownloadError(failures)
    return len(media_items), downloaded, original_count, fallback_count


def download_note_task(batch, data_spider, cookies, note_url, output_root, *, dry_run=False,
                       use_original_images=True, overwrite_images=False, record_file=None,
                       downloaded_note_ids=None, retry_paths=None):
    """A note is complete only after every media item has been saved."""
    note_id = note_url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    payload = {"kind": "xhs_note", "note_url": note_url, "output_root": str(output_root),
               "use_original_images": use_original_images,
               "record_file": str(record_file) if record_file else None}
    cached_note = None
    first_attempt = True
    pending_paths = {Path(path) for path in retry_paths or []}

    def download():
        nonlocal cached_note, first_attempt
        if cached_note is None:
            success, message, cached_note = data_spider.spider_note(note_url, cookies)
            if not success or not cached_note:
                cached_note = None
                raise RuntimeError(f"笔记详情获取失败：{message}")
        replace_images = overwrite_images and first_attempt
        first_attempt = False
        try:
            result = save_note_media(cached_note, output_root, dry_run=dry_run,
                                     use_original_images=use_original_images,
                                     overwrite_images=replace_images, batch=batch, retry_paths=pending_paths)
        except MediaDownloadError as error:
            pending_paths.clear()
            pending_paths.update(error.failed_paths)
            payload["retry_paths"] = [str(path) for path in sorted(pending_paths)]
            raise
        if not dry_run:
            metadata = Path(output_root) / f"{cached_note['note_id']}_info.json"
            metadata.write_text(json.dumps(cached_note, ensure_ascii=False, indent=2), encoding="utf-8")
            if record_file:
                mark_note_downloaded(record_file, cached_note, *result, output_root,
                                     downloaded_note_ids if downloaded_note_ids is not None
                                     else load_downloaded_note_ids(record_file))
        logger.info(f"笔记完成：{note_id}；媒体 {result[0]} 个，新增 {result[1]} 个，原图下载成功 {result[2]} 张，预览图下载成功 {result[3]} 张")
        return result

    return batch.attempt(f"xhs_note:{note_id}", note_url, payload, download)


def timestamp_run_dir(output_base):
    folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    return str(Path(output_base) / folder_name)


def load_downloaded_note_ids(record_file):
    record_path = Path(record_file)
    id_path = record_path.with_name("downloaded_note_ids.txt")
    note_ids = set()

    if record_path.exists():
        with open(record_path, mode="r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    note_id = record.get("note_id")
                except json.JSONDecodeError:
                    note_id = line
                if note_id:
                    note_ids.add(str(note_id))

    if id_path.exists():
        with open(id_path, mode="r", encoding="utf-8-sig") as f:
            for line in f:
                note_id = line.strip().lstrip("\ufeff")
                if note_id:
                    note_ids.add(note_id)

    return note_ids


def mark_note_downloaded(
    record_file,
    note_info,
    media_count,
    downloaded_count,
    original_count,
    fallback_count,
    download_dir,
    downloaded_note_ids,
):
    note_id = str(note_info.get("note_id") or "")
    if not note_id or note_id in downloaded_note_ids:
        return

    record_path = Path(record_file)
    id_path = record_path.with_name("downloaded_note_ids.txt")
    check_and_create_path(record_path.parent)

    record = {
        "note_id": note_id,
        "note_url": note_info.get("note_url"),
        "note_type": note_info.get("note_type"),
        "title": note_info.get("title"),
        "nickname": note_info.get("nickname"),
        "upload_time": note_info.get("upload_time"),
        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        "media_count": media_count,
        "downloaded_count": downloaded_count,
        "original_image_count": original_count,
        "preview_image_count": fallback_count,
        "download_dir": str(download_dir),
    }
    with open(record_path, mode="a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    with open(id_path, mode="a", encoding="utf-8") as f:
        f.write(note_id + "\n")
    downloaded_note_ids.add(note_id)


def main(argv=None):
    args = parse_args(argv)
    output_base = Path(args.output or PROJECT_LIKES_OUTPUT).resolve()
    run_output_root = Path(args.run_dir or timestamp_run_dir(output_base)).resolve()
    record_file = Path(args.record_file or output_base / "downloaded_notes.jsonl").resolve()

    with DownloadBatch.from_arguments("xhs", args) as batch:
        def run():
            cookies = load_or_login_cookies(validate=True)
            api, data_spider = XHS_Apis(), Data_Spider()
            downloaded_ids = load_downloaded_note_ids(record_file)

            def note_task(url, output=run_output_root, original=not args.compressed_images, record=record_file,
                          retry_paths=None):
                existing = downloaded_ids
                if record and Path(record).resolve() != record_file:
                    existing = load_downloaded_note_ids(record)
                return download_note_task(batch, data_spider, cookies, url, output,
                                          dry_run=args.dry_run, use_original_images=original,
                                          overwrite_images=args.overwrite_images, record_file=record,
                                          downloaded_note_ids=existing, retry_paths=retry_paths)

            def scan(cursor="", processed=0, output=run_output_root, record=record_file,
                     limit=args.limit, original=not args.compressed_images):
                user_id = get_current_user_id(api, cookies)
                while True:
                    if limit and processed >= limit:
                        return
                    page_key = f"xhs_page:{cursor}"
                    payload = {"kind": "xhs_likes_page", "cursor": cursor, "processed": processed,
                               "output_root": str(output), "record_file": str(record),
                               "limit": limit, "use_original_images": original}
                    try:
                        success, message, result = api.get_user_like_note_info(user_id, cursor, cookies)
                        if not success:
                            raise RuntimeError(f"获取喜欢列表失败：{message}")
                    except Exception as error:
                        batch.failed(page_key, f"喜欢列表分页 {cursor or '首页'}", payload, error,
                                     lambda c=cursor, n=processed: scan(c, n, output, record, limit, original))
                        return
                    if page_key in batch.failures:
                        batch.succeeded(page_key)
                    data = result.get("data") or {}
                    for liked in data.get("notes") or []:
                        if limit and processed >= limit:
                            return
                        processed += 1
                        note_id = str(liked.get("note_id") or liked.get("id") or "")
                        if note_id in downloaded_ids:
                            if not args.continue_past_downloaded:
                                logger.info(f"遇到已下载笔记 {note_id}，停止增量下载")
                                return
                            continue
                        url = liked_note_url(liked)
                        if not url:
                            batch.failed(f"xhs_invalid:{processed}", f"第 {processed} 条喜欢记录",
                                         {"kind": "invalid_note"}, "喜欢记录缺少 note_id，无法重试")
                            continue
                        note_task(url, output, original, record)
                        if args.delay > 0:
                            time.sleep(args.delay)
                    next_cursor = str(data.get("cursor") or "")
                    if not data.get("has_more") or not next_cursor or next_cursor == cursor:
                        return
                    cursor = next_cursor

            if args.retry_failed:
                for task in read_failure_tasks(args.retry_failed, "xhs"):
                    payload = task["payload"]
                    if payload["kind"] == "xhs_note":
                        note_task(payload["note_url"], Path(payload["output_root"]),
                                  payload.get("use_original_images", True), payload.get("record_file"),
                                  payload.get("retry_paths"))
                    elif payload["kind"] == "xhs_likes_page":
                        # Keep the original partial batch's directory and record file.
                        scan(payload["cursor"], payload.get("processed", 0),
                             Path(payload["output_root"]), Path(payload["record_file"]),
                             payload.get("limit", 0), payload.get("use_original_images", True))
                    elif payload["kind"] == "xhs_likes_start":
                        scan()
                    else:
                        batch.failed(task["key"], task["label"], payload, "此失败项缺少可重试的链接")
            else:
                scan()

        batch.attempt("xhs_likes_start", "加载账号和喜欢列表",
                      {"kind": "xhs_likes_start"}, run)
        return batch.finish(dry_run=args.dry_run)


PROJECT_LIKES_OUTPUT = Path(__file__).resolve().parents[1] / "download_files" / "likes"


if __name__ == "__main__":
    raise SystemExit(main())


