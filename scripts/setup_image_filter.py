"""Prepare and validate local OpenCV person/pose models."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spider.image_filter import PersonLegClassifier
from spider.clip_filter import ClipClothingClassifier


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="预先准备图片筛选模型")
    parser.add_argument("--stockings", action="store_true", help="同时准备黑丝袜实验模型")
    arguments = parser.parse_args()
    PersonLegClassifier()
    ClipClothingClassifier()
    if arguments.stockings:
        ClipClothingClassifier(fashion=True)
    print("人物和腿部筛选模型已就绪。")
