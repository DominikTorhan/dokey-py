import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path

from tools import usage_report


def summary(directory, session, day, counts, bindings, config="fp", version="1.2.3"):
    path = directory / f"usage-summary-{day}-{session}.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "date": day,
                "session": session,
                "version": version,
                "config": config,
                "bindings": bindings,
                "features": {},
                "first_record": f"{day}T09:00:00+00:00",
                "last_record": f"{day}T17:00:00+00:00",
                "session_ended": True,
                "counts": counts,
            }
        ),
        encoding="utf-8",
    )
    return path


def binding(name, count, action="keys", repeat=False):
    return {
        "event": "binding",
        "binding": name,
        "action": action,
        "mode": 1,
        "modifiers": "",
        "repeat": repeat,
        "count": count,
    }


MANIFEST = {
    "prefix.i": "prefix",
    "common.j": "keys",
    "common.k": "keys",
    "two_step.i.j": "keys",
    "two_step.i.k": "keys",
    "two_step.i.m": "command",
}


class TestUsageReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.today = date.today().isoformat()

    def run_report(self, *args):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = usage_report.main(["--logs", str(self.dir), *args])
        self.assertEqual(0, code)
        return out.getvalue()

    def test_counts_sum_across_sessions_and_repeats_stay_separate(self):
        summary(
            self.dir,
            "a" * 32,
            self.today,
            [binding("common.j", 5), binding("common.j", 40, repeat=True)],
            MANIFEST,
        )
        summary(
            self.dir, "b" * 32, self.today, [binding("common.j", 7)], MANIFEST
        )
        text = self.run_report()
        # 5 + 7 deliberate, and the 40 held-key repeats must not inflate the rank
        self.assertIn("12  common.j", text)
        self.assertIn("+40 repeat", text)
        self.assertIn("(12 deliberate, 40 repeat)", text)

    def test_unused_bindings_are_reported_and_prefixes_excluded(self):
        summary(self.dir, "a" * 32, self.today, [binding("common.j", 1)], MANIFEST)
        text = self.run_report()
        # five of the manifest's six entries are unused; prefix.i is not a binding
        self.assertIn("Never used  4 of 5 configured bindings", text)
        self.assertIn("two_step.i", text)
        self.assertIn("common", text)

    def test_section_used_by_nothing_is_called_out_whole(self):
        summary(self.dir, "a" * 32, self.today, [binding("common.j", 1)], MANIFEST)
        text = self.run_report()
        self.assertIn("entirely unused sections", text)
        self.assertRegex(text, r"two_step\.i\s+3 bindings, none used")

    def test_incomplete_actions_do_not_count_as_shortcuts(self):
        summary(
            self.dir,
            "a" * 32,
            self.today,
            [
                binding("common.j", 2),
                binding("prefix.i", 9, action="prefix"),
                binding("two_step.i.z", 4, action="missing_binding"),
            ],
            MANIFEST,
        )
        text = self.run_report()
        self.assertIn("shortcuts  2 completed", text)
        self.assertIn("Chords that resolved to nothing", text)
        self.assertIn("4  two_step.i.z", text)
        self.assertNotIn("9  prefix.i", text)

    def test_changed_keymap_is_flagged_because_unused_may_be_stale(self):
        summary(self.dir, "a" * 32, self.today, [], MANIFEST, config="one")
        summary(self.dir, "b" * 32, self.today, [], MANIFEST, config="two")
        self.assertIn("the keymap changed", self.run_report())

    def test_days_window_excludes_older_snapshots(self):
        old = (date.today() - timedelta(days=30)).isoformat()
        summary(self.dir, "a" * 32, old, [binding("common.k", 99)], MANIFEST)
        summary(self.dir, "b" * 32, self.today, [binding("common.j", 1)], MANIFEST)
        self.assertIn("common.k", self.run_report("--days", "60"))
        self.assertNotIn("common.k", self.run_report("--days", "7"))

    def test_corrupt_snapshot_costs_only_its_own_day(self):
        (self.dir / f"usage-summary-{self.today}-{'c' * 32}.json").write_text("{ bad")
        summary(self.dir, "a" * 32, self.today, [binding("common.j", 3)], MANIFEST)
        self.assertIn("3  common.j", self.run_report())

    def test_empty_directory_reports_failure_without_traceback(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(1, usage_report.main(["--logs", str(self.dir)]))


if __name__ == "__main__":
    unittest.main()
