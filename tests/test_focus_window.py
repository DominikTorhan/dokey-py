import json
import threading
import unittest
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

    def test_invalid_config_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "process.exe::title prefix"):
            Config._parse_config_value_to_event("__focus__<wezterm-gui.exe>")

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
