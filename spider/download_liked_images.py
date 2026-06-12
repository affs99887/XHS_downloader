import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from spider.spider import Data_Spider
from xhs_utils.common_util import load_env
from xhs_utils.data_util import check_and_create_path, download_media, norm_str


def parse_args():
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
    return parser.parse_args()


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
    logger.warning(f"原图地址转换失败，使用预览图: {msg}")
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
                seen.add(url)
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
        return True
    except Exception as exc:
        if media_type == "image" and fallback_url and fallback_url != url:
            logger.warning(f"原图不存在或不可用，使用预览图: {name}, error: {exc}")
            download_media(path, name, fallback_url, media_type)
            return False
        raise


def save_note_media(note_info, output_root, dry_run=False, use_original_images=True, overwrite_images=False):
    media_items = media_items_from_note(note_info, use_original_images)
    if dry_run:
        return len(media_items), 0, 0, 0

    check_and_create_path(output_root)
    downloaded = 0
    original_count = 0
    fallback_count = 0
    for label, url, media_type, fallback_url in media_items:
        name = media_file_stem(note_info, label)
        suffix = "jpg" if media_type == "image" else "mp4"
        file_path = Path(output_root) / f"{name}.{suffix}"
        if file_path.exists():
            if media_type != "image" or not overwrite_images:
                logger.info(f"已存在，跳过: {file_path}")
                continue
        used_primary = download_media_with_fallback(output_root, name, url, media_type, fallback_url)
        if media_type == "image":
            if used_primary:
                original_count += 1
            else:
                fallback_count += 1
        downloaded += 1
    return len(media_items), downloaded, original_count, fallback_count


def timestamp_run_dir(output_base):
    folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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


def main():
    args = parse_args()
    cookies_str = load_env()
    if not cookies_str:
        raise RuntimeError("请先在 .env 中配置 COOKIES")

    output_base = args.output or os.path.abspath(os.path.join(os.path.dirname(__file__), "../download_files/likes"))
    run_output_root = args.run_dir or timestamp_run_dir(output_base)
    record_file = args.record_file or str(Path(output_base) / "downloaded_notes.jsonl")
    downloaded_note_ids = load_downloaded_note_ids(record_file)
    api = XHS_Apis()
    data_spider = Data_Spider()
    user_id = get_current_user_id(api, cookies_str)
    logger.info(f"当前账号 user_id: {user_id}")
    logger.info(f"媒体总目录: {output_base}")
    logger.info(f"本次下载目录: {run_output_root}")
    logger.info(f"已下载记录: {record_file}，已有 {len(downloaded_note_ids)} 条")

    total_notes = 0
    detail_success = 0
    total_media = 0
    downloaded_media = 0
    stopped_on_downloaded = ""

    for liked in iter_liked_notes(api, user_id, cookies_str, args.limit):
        total_notes += 1
        liked_note_id = str(liked.get("note_id") or liked.get("id") or "")
        if liked_note_id and liked_note_id in downloaded_note_ids and not args.continue_past_downloaded:
            stopped_on_downloaded = liked_note_id
            logger.info(f"遇到已下载笔记 {liked_note_id}，停止增量下载")
            break

        note_url = liked_note_url(liked)
        if not note_url:
            logger.warning(f"第 {total_notes} 条喜欢记录缺少 note_id，跳过")
            continue

        success, msg, note_info = data_spider.spider_note(note_url, cookies_str)
        if not success or not note_info:
            logger.warning(f"详情获取失败，跳过: {note_url}, msg: {msg}")
            continue

        detail_success += 1
        try:
            media_count, downloaded_count, original_count, fallback_count = save_note_media(
                note_info,
                run_output_root,
                args.dry_run,
                use_original_images=not args.compressed_images,
                overwrite_images=args.overwrite_images,
            )
            total_media += media_count
            downloaded_media += downloaded_count
            if not args.dry_run:
                mark_note_downloaded(
                    record_file,
                    note_info,
                    media_count,
                    downloaded_count,
                    original_count,
                    fallback_count,
                    run_output_root,
                    downloaded_note_ids,
                )
            logger.info(
                f"[{total_notes}] {note_info['note_id']} {note_info['note_type']} "
                f"媒体 {media_count} 个，新增下载 {downloaded_count} 个，"
                f"原图 {original_count} 张，预览图 {fallback_count} 张"
            )
        except Exception as exc:
            logger.exception(f"媒体保存失败，跳过: {note_url}, error: {exc}")

        if args.delay > 0:
            time.sleep(args.delay)

    logger.info(
        f"完成。喜欢记录 {total_notes} 条，详情成功 {detail_success} 条，"
        f"媒体共 {total_media} 个，新增下载 {downloaded_media} 个"
    )
    if stopped_on_downloaded:
        logger.info(f"本次在已下载笔记处停止: {stopped_on_downloaded}")


if __name__ == "__main__":
    main()
