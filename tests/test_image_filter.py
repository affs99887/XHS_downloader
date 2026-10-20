from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from spider.image_filter import (
    ImageDecision, collect_images, move_without_overwrite, sort_images, visible_leg_segments,
)


class ImageFilterTest(unittest.TestCase):
    def test_leg_requires_adjacent_visible_joints_inside_image(self):
        points = np.zeros((39, 5))
        points[23] = [50, 40, 0, .95, .95]
        points[25] = [50, 70, 0, .95, .95]
        self.assertTrue(visible_leg_segments(points, 100, 100))
        points[25, 1] = 110  # hallucinated knee outside frame
        self.assertFalse(visible_leg_segments(points, 100, 100))
        points[25] = [50, 70, 0, .1, .95]  # hidden knee
        self.assertFalse(visible_leg_segments(points, 100, 100))
        points[25] = [50, 41, 0, .95, .95]  # no meaningful segment
        self.assertFalse(visible_leg_segments(points, 100, 100))

    def test_sort_preserves_relative_paths_and_never_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory(prefix="图片筛选 ") as directory:
            root = Path(directory)
            source = root / "作者" / "a.jpg"
            source.parent.mkdir()
            source.write_bytes(b"new picture")
            existing = root / "弃用" / "作者" / "a.jpg"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"previous picture")
            moved = move_without_overwrite(source, root, "弃用")
            self.assertEqual(existing.read_bytes(), b"previous picture")
            self.assertEqual(moved.read_bytes(), b"new picture")
            self.assertFalse(source.exists())
            self.assertEqual(moved.name, "a_1.jpg")

    def test_uncertain_images_have_separate_review_folder_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keep, discard, review, broken = [root / f"{name}.jpg" for name in ("keep", "discard", "review", "broken")]
            for path in (keep, discard, review, broken):
                path.write_bytes(b"original")
            classifier = Mock()
            classifier.classify.side_effect = [ImageDecision("keep", "legs", True, True),
                                               ImageDecision("discard", "landscape", False),
                                               ImageDecision("review", "uncertain"), OSError("corrupt image")]
            counts = sort_images({path: root for path in (keep, discard, review, broken)}, root, classifier=classifier)
            self.assertEqual(counts, {"keep": 1, "discard": 1, "review": 1, "errors": 1})
            self.assertTrue(keep.exists())
            self.assertTrue(broken.exists())
            self.assertTrue((root / "弃用" / discard.name).exists())
            self.assertTrue((root / "待复核" / review.name).exists())
            records = [json.loads(line) for line in (root / "image_classification.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["action"], "error")
            self.assertEqual(set(collect_images(root)), {keep, broken})

    def test_unavailable_model_keeps_every_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "photo.jpg"
            image.write_bytes(b"untouched")
            with patch("spider.image_filter.PersonLegClassifier", side_effect=OSError("offline")):
                result = sort_images({image: root}, root)
            self.assertEqual(result["errors"], 1)
            self.assertEqual(image.read_bytes(), b"untouched")
            self.assertFalse((root / "弃用").exists())

    def test_preview_writes_decisions_without_moving_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "photo.jpg"
            image.write_bytes(b"original")
            classifier = Mock()
            classifier.classify.return_value = ImageDecision("discard", "not a match")
            result = sort_images({image: root}, root, classifier=classifier, preview=True)
            self.assertEqual(result["discard"], 1)
            self.assertTrue(image.exists())
            self.assertFalse((root / "弃用").exists())

    def test_moving_an_outside_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "downloads"
            root.mkdir()
            source = Path(directory) / "outside.jpg"
            source.write_bytes(b"outside")
            with self.assertRaises(ValueError):
                move_without_overwrite(source, root, "弃用")
            self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
