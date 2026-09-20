"""Regression tests for xhs_engagement metric normalization."""

from __future__ import annotations

import importlib.util
import io
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "crews/main/skills/expert-xhs/tools/xhs-engagement/scripts/xhs_engagement.py"
SPEC = importlib.util.spec_from_file_location("xhs_engagement", SCRIPT_PATH)
assert SPEC and SPEC.loader
xhs_engagement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(xhs_engagement)


class StatsToMetricsTests(unittest.TestCase):
    def test_maps_creator_stats_in_the_documented_column_order(self) -> None:
        metrics = xhs_engagement.stats_to_metrics([101, 7, 23, 5, 2])

        self.assertEqual(
            metrics,
            {
                "views": 101,
                "comments": 7,
                "likes": 23,
                "collects": 5,
                "shares": 2,
            },
        )

    def test_pads_missing_trailing_columns_with_zeroes(self) -> None:
        metrics = xhs_engagement.stats_to_metrics([101, 7])

        self.assertEqual(
            metrics,
            {
                "views": 101,
                "comments": 7,
                "likes": 0,
                "collects": 0,
                "shares": 0,
            },
        )


class FetchMetricPropagationTests(unittest.TestCase):
    def test_fetch_writes_metrics_in_creator_backend_column_order(self) -> None:
        expected_metrics = {
            "views": 101,
            "comments": 7,
            "likes": 23,
            "collects": 5,
            "shares": 2,
        }
        output = io.StringIO()
        args = type("Args", (), {"row_id": 42, "title": None})()

        with (
            mock.patch.object(
                xhs_engagement,
                "lookup_published_row",
                return_value={"id": 42, "title": "测试笔记", "publish_url": "https://example.test/note"},
            ),
            mock.patch.object(
                xhs_engagement,
                "open_note_manager_and_wait",
                return_value=([{"title": "测试笔记", "stats": [101, 7, 23, 5, 2]}], 1),
            ),
            mock.patch.object(xhs_engagement, "camoufox_close"),
            mock.patch.object(xhs_engagement, "update_metrics_row", return_value={"ok": True}) as update_metrics,
            mock.patch("sys.stdout", output),
        ):
            xhs_engagement.cmd_fetch(args)

        update_metrics.assert_called_once_with(42, expected_metrics)
        self.assertEqual(
            xhs_engagement.json.loads(output.getvalue())["metrics"],
            expected_metrics,
        )

    def test_update_writes_metrics_to_the_correct_named_columns(self) -> None:
        metrics = {
            "views": 101,
            "comments": 7,
            "likes": 23,
            "collects": 5,
            "shares": 2,
        }
        completed = xhs_engagement.subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )

        with (
            mock.patch.object(xhs_engagement, "UPDATE_METRICS_SH", SCRIPT_PATH),
            mock.patch.object(xhs_engagement.subprocess, "run", return_value=completed) as run,
        ):
            result = xhs_engagement.update_metrics_row(42, metrics)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            run.call_args.args[0],
            [
                str(SCRIPT_PATH),
                "--platform", "xhs",
                "--id", "42",
                "--views", "101",
                "--comments", "7",
                "--likes", "23",
                "--favorites", "5",
                "--shares", "2",
            ],
        )

if __name__ == "__main__":
    unittest.main()
