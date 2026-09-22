import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import usage
from app.app import App, WindowFocusInterface
from app.config import Config
from app.events import FocusWindowEvent
from app.keys import Keys
from app.mouse_config import MouseConfig
from tests.test_side_effects import ScriptedListener, CONFIG_PATH, MOUSE_CONFIG_PATH


class TestFocusWindow(unittest.TestCase):
    def test_config_value_parses_process_and_title_prefix(self):
        event = Config._parse_config_value_to_event(
            "__focus__<wezterm-gui.exe::A | >"
        )
        self.assertIsInstance(event, FocusWindowEvent)
        self.assertEqual("wezterm-gui.exe", event.process)
        self.assertEqual("A |", event.title_prefix)

    def test_invalid_config_value_is_logged_and_dropped(self):
        for value in (
            "__focus__<wezterm-gui.exe>",
            "__focus__<::A |>",
            "__focus__<wezterm-gui.exe::>",
        ):
            with self.subTest(value=value):
                with self.assertLogs("app.config", "ERROR"):
                    events = Config._convert_dict_events({"d1": value, "d2": "up"})
                self.assertNotIn(Keys.D1, events)
                self.assertIn(Keys.D2, events)

    def test_invalid_user_config_does_not_stop_startup(self):
        with tempfile.TemporaryDirectory() as home:
            dokey = Path(home) / ".dokey"
            dokey.mkdir()
            (dokey / "user_config.yaml").write_text(
                "a:\n  d1: __focus__<wezterm-gui.exe>\n"
            )
            with (
                patch("app.config.dokey_dir", return_value=dokey),
                self.assertLogs("app.config", "ERROR"),
            ):
                config = Config.from_file(CONFIG_PATH)
        self.assertIsNone(config.get_two_step_event(Keys.A, Keys.D1))

    def test_focus_runs_on_worker_with_original_binding(self):
        calls = []
        caller = threading.current_thread()

        def focus(process, title_prefix):
            calls.append((process, title_prefix, threading.current_thread()))
            return True

        listener = ScriptedListener(
            [(Keys.A, "d"), (Keys.A, "u"), (Keys.D1, "d")]
        )
        with patch.object(Config, "try_load_users_config"):
            app = App(
                CONFIG_PATH,
                MOUSE_CONFIG_PATH,
                listener,
                window_focus_interface=WindowFocusInterface(focus),
            )
        app.config.two_step_events[Keys.A][Keys.D1] = FocusWindowEvent(
            "wezterm-gui.exe", "A |"
        )
        with patch.object(usage, "record") as record:
            app.main()

        self.assertEqual(1, len(calls))
        self.assertEqual(("wezterm-gui.exe", "A |"), calls[0][:2])
        self.assertIsNot(caller, calls[0][2])
        self.assertIsInstance(listener.returned[-1], FocusWindowEvent)
        record.assert_any_call(
            "window_focus", binding="two_step.a.d1", success=True
        )

    def test_usage_manifest_does_not_expose_focus_target(self):
        with patch.object(Config, "try_load_users_config"):
            config = Config.from_file(CONFIG_PATH)
        config.two_step_events[Keys.A][Keys.D1] = FocusWindowEvent(
            "private.exe", "Private title"
        )
        _, manifest = usage.configuration(
            config, MouseConfig.from_file(MOUSE_CONFIG_PATH)
        )
        self.assertEqual("focus", manifest["two_step.a.d1"])
        self.assertNotIn("private", json.dumps(manifest).casefold())


if __name__ == "__main__":
    unittest.main()
