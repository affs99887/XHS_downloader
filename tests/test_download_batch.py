import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spider.download_batch import DownloadBatch, read_failure_tasks


class DownloadBatchTest(unittest.TestCase):
    def test_failure_is_persisted_and_retry_only_runs_failed_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            fail = [True]

            def action():
                calls.append("bad")
                if fail[0]:
                    raise OSError("network disconnected")

            with DownloadBatch("test", log_dir=Path(directory), image_filter="off") as batch:
                batch.attempt("bad", "bad item", {"kind": "media"}, action)
                batch.attempt("good", "good item", {}, lambda: calls.append("good"))
                self.assertEqual(len(read_failure_tasks(batch.failure_file, "test")), 1)
                fail[0] = False
                with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y") as prompt:
                    self.assertEqual(batch.finish(), 0)
                prompt.assert_called_once()
                self.assertEqual(calls, ["bad", "good", "bad"])
                self.assertEqual(read_failure_tasks(batch.failure_file, "test"), [])
            self.assertTrue(json.loads((batch.directory / "summary.json").read_text())["completed"])

    def test_piped_input_never_blocks_and_unresolved_failures_return_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            with DownloadBatch("test", log_dir=Path(directory), image_filter="off") as batch:
                batch.attempt("bad", "bad", {}, lambda: 1 / 0)
                with patch("sys.stdin.isatty", return_value=False), patch("builtins.input") as prompt:
                    self.assertEqual(batch.finish(), 1)
                prompt.assert_not_called()
                self.assertEqual(len(read_failure_tasks(batch.failure_file, "test")), 1)

    def test_declining_keeps_the_manifest_and_successful_batches_do_not_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            with DownloadBatch("test", log_dir=Path(directory), image_filter="off") as batch:
                with patch("builtins.input") as prompt:
                    self.assertEqual(batch.finish(), 0)
                prompt.assert_not_called()
            with DownloadBatch("test", log_dir=Path(directory), image_filter="off") as batch:
                batch.failed("bad", "bad", {}, "timeout", lambda: None)
                with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="n"):
                    self.assertEqual(batch.finish(), 1)
                self.assertTrue(batch.failure_file.is_file())

    def test_interruption_still_writes_summary_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                with DownloadBatch("test", log_dir=Path(directory)) as batch:
                    batch.failed("bad", "bad", {}, "timeout")
                    raise KeyboardInterrupt()
            summary = json.loads((batch.directory / "summary.json").read_text())
            self.assertFalse(summary["completed"])
            self.assertEqual(summary["failed_tasks"], 1)


if __name__ == "__main__":
    unittest.main()
