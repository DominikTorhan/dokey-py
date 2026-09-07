import json
import logging
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import usage
from app.app import App, OSEvent, HelpInterface, MouseInterface, DiagnosticsInterface
from app.app_state import INSERT, MOUSE
from app.config import Config
from app.events import CMDEvent, WriteEvent
from app.keys import Keys
from app.mouse_config import MouseConfig
from tests.test_side_effects import ScriptedListener, CONFIG_PATH, MOUSE_CONFIG_PATH


class TestUsage(unittest.TestCase):
    def test_fingerprint_covers_overrides_without_exposing_contents(self):
        with patch.object(Config, "try_load_users_config"):
            config = Config.from_file(CONFIG_PATH)
        mouse = MouseConfig.from_file(MOUSE_CONFIG_PATH)
        before, _ = usage.configuration(config, mouse)
        config.two_step_events[Keys.A][Keys.A] = CMDEvent("private command")
        config.two_step_events[Keys.A][Keys.B] = WriteEvent("private text")
        after, manifest = usage.configuration(config, mouse)
        self.assertNotEqual(before, after)
        self.assertEqual("command", manifest["two_step.a.a"])
        self.assertEqual("text", manifest["two_step.a.b"])
        self.assertNotIn("private", json.dumps(manifest))
        self.assertEqual(after, usage.configuration(config, mouse)[0])
        mouse.positions["q"] = [50, 50]
        self.assertNotEqual(after, usage.configuration(config, mouse)[0])

    def test_repeat_counts_daily_rollover_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / ("usage-summary-2020-01-01-" + "a" * 32 + ".json")
            old.write_text("{}")
            unrelated = root / "usage-summary-2020-01-01-not-ours.json"
            unrelated.write_text("{}")
            handler = usage.UsageHandler(root)

            def emit(day, **fields):
                record = logging.makeLogRecord({"usage": fields})
                record.created = datetime(2026, 9, day, tzinfo=timezone.utc).timestamp()
                handler.handle(record)

            try:
                emit(
                    7,
                    event="session_start",
                    config="fingerprint",
                    bindings={"common.j": "keys"},
                    features={"help": False},
                )
                for repeat in (False, True, True):
                    emit(
                        7, event="binding", binding="common.j",
                        action="keys", repeat=repeat,
                    )
                emit(
                    8, event="binding", binding="common.j",
                    action="keys", repeat=False,
                )
                emit(8, event="session_end")
            finally:
                handler.close()
            summaries = sorted(root.glob("usage-summary-2026*.json"))
            self.assertEqual(2, len(summaries))
            first, second = [json.loads(p.read_text()) for p in summaries]
            self.assertEqual(
                {False: 1, True: 2},
                {item["repeat"]: item["count"] for item in first["counts"]},
            )
            self.assertEqual(1, second["counts"][0]["count"])
            self.assertTrue(second["session_ended"])
            self.assertEqual("fingerprint", second["config"])
            self.assertEqual({"common.j": "keys"}, second["bindings"])
            self.assertFalse(old.exists())
            self.assertTrue(unrelated.exists())
            details = [
                json.loads(line)
                for line in (root / "usage.jsonl").read_text().splitlines()
            ]
            self.assertEqual(6, len(details))
            self.assertTrue(
                all(item["session"] == usage.SESSION_ID for item in details)
            )

    def test_actions_are_attributed_without_logging_plain_typing_or_payloads(self):
        with patch.object(Config, "try_load_users_config"):
            app = App(CONFIG_PATH, MOUSE_CONFIG_PATH, ScriptedListener([]))
        app.config.two_step_events[Keys.A][Keys.A] = WriteEvent("private text")

        def key(key, up=False, repeat=False):
            event = OSEvent()
            event.key, event.is_key_up, event.is_repeat = key, up, repeat
            return app.handle_keyboard_event(event)

        with patch.object(usage, "record") as record:
            app.state.mode = INSERT
            key(Keys.P)
            self.assertFalse(record.called)
            app.state.first_step = Keys.T
            key(Keys.CAPS)
            key(Keys.E)
            key(Keys.E, repeat=True)
            key(Keys.E, up=True)
            key(Keys.CAPS, up=True)
            app.state.mode = 1
            key(Keys.A)
            key(Keys.A)
        fields = [
            call.kwargs for call in record.call_args_list if call.args[0] == "binding"
        ]
        self.assertEqual(
            ["special.e", "special.e", "prefix.a", "two_step.a.a"],
            [item["binding"] for item in fields],
        )
        self.assertEqual([False, True], [item["repeat"] for item in fields[:2]])
        self.assertEqual("text", fields[-1]["action"])
        self.assertNotIn("private text", str(record.call_args_list))

    def test_overlay_transitions_are_logged_once_after_ui_calls(self):
        calls = []

        def show():
            calls.append("show")

        def hide():
            calls.append("hide")

        with patch.object(Config, "try_load_users_config"):
            app = App(
                CONFIG_PATH,
                MOUSE_CONFIG_PATH,
                ScriptedListener([]),
                help_interface=HelpInterface(show, hide),
                mouse_interface=MouseInterface(show, hide, hide),
                diagnostics_interface=DiagnosticsInterface(show, hide),
            )
        with patch.object(usage, "record") as record:
            app._apply_side_effects(MOUSE, Keys.NONE, True, True, None, False)
            app._apply_side_effects(MOUSE, Keys.NONE, True, True, None, False)
            app._apply_side_effects(1, Keys.NONE, False, False, None, False)
        self.assertEqual(6, record.call_count)
        self.assertEqual(
            [True] * 3 + [False] * 3,
            [call.kwargs["visible"] for call in record.call_args_list],
        )
        self.assertEqual(9, len(calls))

    def test_command_failure_does_not_log_command_contents(self):
        with (
            patch(
                "app.app.subprocess.Popen", side_effect=OSError(2, "private command")
            ),
            patch.object(usage, "record") as record,
            self.assertLogs("app.app", level="ERROR") as logs,
        ):
            App._run_command("private command", "two_step.a.a")
        self.assertNotIn("private command", "\n".join(logs.output))
        record.assert_called_once_with(
            "command_launch", binding="two_step.a.a", success=False
        )

    def test_session_and_deferred_command_keep_the_original_binding(self):
        listener = ScriptedListener([
            (Keys.A, "d"), (Keys.A, "u"), (Keys.B, "d"), (Keys.B, "u"),
            (Keys.J, "d"), (Keys.CAPS, "d"), (Keys.F, "d"), (Keys.CAPS, "u"),
        ])
        with patch.object(Config, "try_load_users_config"):
            app = App(CONFIG_PATH, MOUSE_CONFIG_PATH, listener)
        app.config.two_step_events[Keys.A][Keys.B] = CMDEvent("private command")
        with (
            patch("app.app.subprocess.Popen"),
            patch.object(usage, "record") as record,
        ):
            app.main()
        self.assertEqual("session_start", record.call_args_list[0].args[0])
        self.assertEqual("session_end", record.call_args_list[-1].args[0])
        self.assertTrue(record.call_args_list[-1].kwargs["worker_drained"])
        self.assertFalse(any(record.call_args_list[0].kwargs["features"].values()))
        record.assert_any_call("mode", previous=1, current=2)
        record.assert_any_call(
            "command_launch", binding="two_step.a.b", success=True
        )
        self.assertNotIn("private command", str(record.call_args_list))
