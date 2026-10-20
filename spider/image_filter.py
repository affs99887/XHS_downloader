"""Local person / visible-leg filtering; images never leave this computer."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIRECTORY = PROJECT_ROOT / ".runtime" / "models" / "image_filter"
OPENCV_ZOO_COMMIT = "47534e27c9851bb1128ccc0102f1145e27f23f98"
MODELS = {
    "person": ("person_detection_mediapipe", "person_detection_mediapipe_2023mar.onnx",
               "47fd5599d6fa17608f03e0eb0ae230baa6e597d7e8a2c8199fe00abea55a701f", 11990159),
    "pose": ("pose_estimation_mediapipe", "pose_estimation_mediapipe_2023mar.onnx",
             "9d89c599319a18fb7d2e28451a883476164543182bafca5f09eb2cf767ed2f3f", 5557238),
}
SORTED_FOLDERS = ("弃用", "待复核")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def ensure_model(kind: str, directory: Path = MODEL_DIRECTORY) -> Path:
    group, filename, expected_hash, expected_size = MODELS[kind]
    relative = f"models/{group}/{filename}"
    urls = [
        f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{OPENCV_ZOO_COMMIT}/{relative}",
        f"https://huggingface.co/opencv/opencv_zoo/resolve/main/{relative}",
    ]
    return download_verified(filename, expected_hash, expected_size, urls, directory)


def download_verified(filename, expected_hash, expected_size, urls, directory=MODEL_DIRECTORY) -> Path:
    import requests

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.is_file() and destination.stat().st_size == expected_size:
        if hashlib.sha256(destination.read_bytes()).hexdigest() == expected_hash:
            return destination
    logger.info(f"首次准备本地图片筛选模型：{filename}（{expected_size / 1024 / 1024:.1f} MB）")
    temporary = destination.with_name(destination.name + "." + uuid4().hex + ".part")
    errors = []
    try:
        for url in urls:
            try:
                digest = hashlib.sha256()
                size = 0
                with requests.get(url, stream=True, timeout=(10, 30)) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_content(1024 * 256):
                            size += len(chunk)
                            if size > expected_size:
                                raise ValueError("模型文件大小异常")
                            digest.update(chunk)
                            stream.write(chunk)
                if size != expected_size or digest.hexdigest() != expected_hash:
                    raise ValueError("模型 SHA-256 校验失败")
                temporary.replace(destination)
                return destination
            except (OSError, ValueError, requests.RequestException) as error:
                errors.append(str(error))
        raise RuntimeError(f"模型准备失败：{filename}；{'；'.join(errors)}")
    finally:
        temporary.unlink(missing_ok=True)


@dataclass
class ImageDecision:
    action: str  # keep / discard / review
    reason: str
    person: bool | None = None
    visible_legs: bool | None = None
    confidence: float | None = None
    backend: str = "opencv-mediapipe"
    similarities: dict | None = None
    margin: float | None = None


def visible_leg_segments(landmarks, width: int, height: int, threshold: float = 0.65) -> bool:
    """Require two adjacent, visible, in-frame joints on the same leg."""
    import numpy as np

    def visible(index):
        x, y, _, visibility, presence = landmarks[index]
        return (visibility >= threshold and presence >= threshold
                and 0 <= x < width and 0 <= y < height)

    for first, second in ((23, 25), (25, 27), (24, 26), (26, 28)):
        if visible(first) and visible(second):
            length = np.linalg.norm(landmarks[first, :2] - landmarks[second, :2])
            if length >= 0.04 * max(width, height):
                return True
    return False


class PersonLegClassifier:
    def __init__(self, mode="legs"):
        from vendor.opencv_pose.mp_persondet import MPPersonDet
        from vendor.opencv_pose.mp_pose import MPPose

        self.mode = mode
        self.semantic = None
        self.semantic_error = None
        self.detector = MPPersonDet(str(ensure_model("person")), scoreThreshold=0.35)
        self.pose = MPPose(str(ensure_model("pose")), confThreshold=0.5) if mode != "person" else None

    def semantic_decision(self, path, *, known_legs=False):
        from spider.clip_filter import ClipClothingClassifier

        if self.semantic_error is not None:
            raise RuntimeError(self.semantic_error)
        if self.semantic is None:
            try:
                self.semantic = ClipClothingClassifier(fashion=self.mode == "stockings")
            except Exception as error:
                self.semantic_error = str(error)
                raise
        return self.semantic.classify(path, self.mode, known_legs=known_legs)

    def classify(self, path: Path) -> ImageDecision:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps

        # Pillow handles Chinese paths, EXIF orientation and formats with a .jpg suffix.
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail((1280, 1280))
            frame = cv2.cvtColor(np.asarray(source), cv2.COLOR_RGB2BGR)
        height, width = frame.shape[:2]
        detections = self.detector.infer(frame)
        if len(detections) == 0:
            return self.semantic_decision(path)
        score = float(max(person[-1] for person in detections))
        confident = [person for person in detections if person[-1] >= 0.65]
        if not confident:
            return self.semantic_decision(path)
        if self.mode == "person":
            return ImageDecision("keep", "检测到人物（人物筛选模式）", person=True, confidence=score)

        for person in confident[:10]:
            # Upstream preprocessing changes the supplied ROI in place.
            pose = self.pose.infer(frame, person.copy())
            if pose is None:
                continue
            landmarks, confidence = pose[1], float(pose[-1])
            if visible_leg_segments(landmarks, width, height):
                if self.mode == "stockings":
                    return self.semantic_decision(path, known_legs=True)
                return ImageDecision("keep", "检测到人物及可见腿部", True, True, confidence)
        return self.semantic_decision(path)


def sorted_media_exists(path: Path, root: Path) -> bool:
    path, root = Path(path), Path(root)
    if path.is_file() and path.stat().st_size > 0:
        return True
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any((root / folder / relative).is_file() for folder in SORTED_FOLDERS)


def move_without_overwrite(source: Path, root: Path, folder: str) -> Path:
    """Keep relative paths and reserve targets exclusively before copying."""
    source, root = source.absolute(), root.resolve()
    if folder not in SORTED_FOLDERS:
        raise ValueError("未知分类目录")
    if source.is_symlink() or not source.resolve().is_relative_to(root):
        raise ValueError(f"图片路径不在下载目录内：{source}")
    relative = source.relative_to(root)
    if any(part in SORTED_FOLDERS for part in relative.parts):
        raise ValueError("不重复移动已分类文件")
    destination = root / folder / relative
    if not destination.parent.resolve().is_relative_to(root):
        raise ValueError("分类目录不在下载目录内")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for index in range(10000):
        candidate = destination if index == 0 else destination.with_name(f"{destination.stem}_{index}{destination.suffix}")
        try:
            stream = candidate.open("xb")
        except FileExistsError:
            continue
        try:
            with stream, source.open("rb") as original:
                shutil.copyfileobj(original, stream)
            shutil.copystat(source, candidate)
            source.unlink()
            return candidate
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
    raise RuntimeError(f"同名文件过多：{destination}")


def sort_images(images: dict[Path, Path], report_directory: Path, *, mode="legs", classifier=None, preview=False) -> dict[str, int]:
    counts = {"keep": 0, "discard": 0, "review": 0, "errors": 0}
    report_path = Path(report_directory) / "image_classification.jsonl"
    try:
        classifier = classifier or PersonLegClassifier(mode)
    except Exception as error:
        # Downloaded originals stay in place if models are unavailable.
        logger.error(f"图片筛选暂不可用，保留全部原文件：{error}")
        counts["errors"] = len(images)
        with report_path.open("a", encoding="utf-8") as report:
            for path in images:
                report.write(json.dumps({"source": str(path), "destination": str(path), "mode": mode,
                                         "action": "error", "reason": str(error)}, ensure_ascii=False) + "\n")
        return counts
    rules = {"legs": "人物且有可见腿部", "person": "人物", "stockings": "人物且穿黑丝袜（实验）"}
    logger.info(f"开始本地图片筛选：{len(images)} 张，规则：{rules[mode]}")
    if preview:
        logger.info("当前为筛选预览：只生成判断报告。")
    with report_path.open("a", encoding="utf-8") as report:
        for index, (path, root) in enumerate(images.items(), 1):
            destination = path
            try:
                decision = classifier.classify(path)
                if decision.action not in {"keep", "discard", "review"}:
                    raise ValueError("分类器返回未知操作")
                if decision.action != "keep":
                    folder = "弃用" if decision.action == "discard" else "待复核"
                    destination = (root / folder / path.relative_to(root)) if preview else move_without_overwrite(path, root, folder)
                counts[decision.action] += 1
                record = {"source": str(path), "destination": str(destination), "mode": mode,
                          "preview": preview, **asdict(decision)}
            except Exception as error:
                counts["errors"] += 1
                logger.warning(f"图片筛选失败，保留原文件：{path}；{error}")
                record = {"source": str(path), "destination": str(path), "mode": mode,
                          "action": "error", "reason": str(error)}
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            report.flush()
            if index % 50 == 0:
                logger.info(f"图片筛选进度：{index}/{len(images)}")
    logger.info(f"图片筛选完成：保留 {counts['keep']}，弃用 {counts['discard']}，待复核 {counts['review']}，失败 {counts['errors']}；报告：{report_path}")
    return counts


def collect_images(root: Path) -> dict[Path, Path]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"图片目录不存在：{root}")
    return {path: root for path in sorted(root.rglob("*"))
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_SUFFIXES
            and not any(part in SORTED_FOLDERS for part in path.relative_to(root).parts)}
