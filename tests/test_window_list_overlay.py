import threading
import unittest

from app.app import App, WindowListInterface
from app.app_state import AppState
from app.config import Config
from app.events import DoKeyEvent
from app.key_processor import KeyProcessor
from app.keys import Keys
from app.mouse_config import MouseConfig
from app.window_inventory_format import format_inventory
from tests.test_side_effects import CONFIG_PATH, MOUSE_CONFIG_PATH, ScriptedListener


def make_processor():
    config = Config.from_file(CONFIG_PATH)
    state = AppState()
    processor = KeyProcessor(config, MouseConfig.from_file(MOUSE_CONFIG_PATH), state)
    return config, state, processor


class TestWindowListKeys(unittest.TestCase):
    def setUp(self):
        self.config, self.state, self.processor = make_processor()

    def test_special_plus_close_bracket_opens_and_refreshes(self):
        self.state.is_special_down = True
        event = self.processor.process(Keys.SQUARE_BRACKET_CLOSE)
        self.assertTrue(event.prevent_key_process)
        self.assertTrue(self.state.window_list_active)
        self.assertEqual(1, self.state.window_list_revision)
        self.assertEqual("control.window_list", self.processor.binding_id)

        self.processor.process(Keys.SQUARE_BRACKET_CLOSE)
        self.assertEqual(2, self.state.window_list_revision)

    def test_bare_close_bracket_does_not_open(self):
        self.processor.process(Keys.SQUARE_BRACKET_CLOSE)
        self.assertFalse(self.state.window_list_active)

    def test_bare_escape_closes_but_special_escape_still_exits(self):
        self.state.window_list_active = True
        event = self.processor.process(Keys.ESC)
        self.assertTrue(event.prevent_key_process)
        self.assertFalse(self.state.window_list_active)

        self.state.window_list_active = True
        self.state.is_special_down = True
        event = self.processor.process(Keys.ESC)
        self.assertIsInstance(event, DoKeyEvent)

    def test_opening_overlays_is_mutually_exclusive(self):
        self.state.keyboard_active = True
        self.state.is_special_down = True
        self.processor.process(Keys.SQUARE_BRACKET_CLOSE)
        self.assertFalse(self.state.keyboard_active)
        self.assertTrue(self.state.window_list_active)

        self.processor.process(self.config.keyboard_key)
        self.assertTrue(self.state.keyboard_active)
        self.assertFalse(self.state.window_list_active)

    def test_navigation_scrolls_and_is_swallowed(self):
        self.state.window_list_active = True
        event = self.processor.process(Keys.PAGE_DOWN)
        self.assertEqual(21, self.state.window_list_scroll)
        self.assertTrue(event.prevent_key_process)
        self.assertEqual("control.window_list_scroll", self.processor.binding_id)

        self.processor.process(Keys.HOME)
        self.assertEqual(1, self.state.window_list_scroll)


class TestWindowListWiring(unittest.TestCase):
    def test_show_and_hide_run_on_worker_with_stable_revision(self):
        calls = []
        caller = threading.current_thread()

        def show(revision, scroll):
            calls.append(("show", revision, scroll, threading.current_thread()))

        def hide():
            calls.append(("hide", None, None, threading.current_thread()))

        listener = ScriptedListener(
            [
                (Keys.CAPS, "d"),
                (Keys.SQUARE_BRACKET_CLOSE, "d"),
                (Keys.SQUARE_BRACKET_CLOSE, "u"),
                (Keys.CAPS, "u"),
                (Keys.ESC, "d"),
            ]
        )
        app = App(
            CONFIG_PATH,
            MOUSE_CONFIG_PATH,
            listener,
            window_list_interface=WindowListInterface(show, hide),
        )
        app.main()

        shows = [call for call in calls if call[0] == "show"]
        self.assertTrue(shows)
        self.assertTrue(all(call[1] == 1 for call in shows))
        self.assertTrue(any(call[0] == "hide" for call in calls))
        self.assertTrue(all(call[3] is not caller for call in calls))


class TestFormatting(unittest.TestCase):
    def test_formats_windows_browser_tabs_and_wezterm_panes(self):
        text = format_inventory(
            {
                "windows": [
                    {
                        "title": "Editor",
                        "process": "editor.exe",
                        "pid": 12,
                        "hwnd": 255,
                        "class": "EditorWindow",
                        "bounds": [10, 20, 810, 620],
                        "state": "maximized",
                        "foreground": True,
                    }
                ],
                "browser_tabs": [
                    {
                        "port": 9222,
                        "title": "Docs",
                        "url": "https://example.test",
                        "type": "page",
                        "id": "target-1",
                    }
                ],
                "wezterm_panes": [
                    {
                        "window_id": 1,
                        "tab_id": 2,
                        "pane_id": 3,
                        "title": "shell",
                        "workspace": "default",
                        "cwd": "file:///C:/dev",
                    }
                ],
            }
        )
        for expected in (
            "Editor",
            "editor.exe",
            "800x600",
            "Docs",
            "https://example.test",
            "tab=2",
            "shell",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
