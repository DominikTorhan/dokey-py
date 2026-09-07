import threading
import unittest
from pathlib import Path

from app.app import App, KeyboardInterface, TrayAppInterface
from app.app_state import AppState
from app.config import Config
from app.events import DoKeyEvent, SendEvent
from app.key_processor import KeyProcessor
from app.keyboard_layout import TABS
from app.keys import Keys
from app.mouse_config import MouseConfig
from tests.test_side_effects import CONFIG_PATH, MOUSE_CONFIG_PATH, ScriptedListener


def make_processor():
    config = Config.from_file(CONFIG_PATH)
    state = AppState()
    processor = KeyProcessor(config, MouseConfig.from_file(MOUSE_CONFIG_PATH), state)
    return config, state, processor


class TestOpenAndClose(unittest.TestCase):
    """Caps + ' opens the cheat sheet; a bare ESC closes it."""

    def setUp(self):
        self.config, self.state, self.processor = make_processor()

    def test_special_plus_the_keyboard_key_opens_it(self):
        self.state.is_special_down = True
        event = self.processor.process(key=self.config.keyboard_key)
        self.assertTrue(self.state.keyboard_active)
        self.assertTrue(event.prevent_key_process, "the trigger must be swallowed")
        self.assertEqual("control.keyboard", self.processor.binding_id)
        self.assertEqual("keyboard", self.processor.action)

    def test_the_keyboard_key_alone_does_not_open_it(self):
        self.processor.process(key=self.config.keyboard_key)
        self.assertFalse(self.state.keyboard_active)

    def test_key_up_never_toggles_it(self):
        self.state.is_special_down = True
        self.processor.process(key=self.config.keyboard_key, is_key_up=True)
        self.assertFalse(self.state.keyboard_active)

    def test_escape_closes_it(self):
        self.state.keyboard_active = True
        event = self.processor.process(key=Keys.ESC)
        self.assertFalse(self.state.keyboard_active)
        self.assertTrue(event.prevent_key_process)

    def test_special_plus_escape_still_exits_dokey(self):
        # Caps+ESC is the exit key; opening the sheet must not steal it
        self.state.keyboard_active = True
        self.state.is_special_down = True
        event = self.processor.process(key=Keys.ESC)
        self.assertIsInstance(event, DoKeyEvent)
        self.assertEqual("exit", event.event_type)
        self.assertTrue(self.state.keyboard_active, "still open; DoKey is quitting")

    def test_escape_is_untouched_when_the_sheet_is_closed(self):
        event = self.processor.process(key=Keys.ESC)
        self.assertFalse(self.state.keyboard_active)
        self.assertNotIsInstance(event, DoKeyEvent)

    def test_other_keys_keep_working_while_it_is_open(self):
        # it is a reference to read, not a mode that traps the keyboard
        self.state.keyboard_active = True
        event = self.processor.process(key=Keys.J)
        self.assertIsInstance(event, SendEvent)
        self.assertEqual([Keys.DOWN], event.send)
        self.assertTrue(self.state.keyboard_active)

    def test_opening_it_does_not_drop_out_of_insert_mode(self):
        self.state.is_special_down = True
        self.processor.process(key=self.config.keyboard_key)
        self.assertTrue(self.state.prevent_prev_mode_on_special_up)


class TestTabNavigation(unittest.TestCase):
    def setUp(self):
        self.config, self.state, self.processor = make_processor()
        self.state.keyboard_active = True

    def test_right_and_left_move_between_tabs(self):
        event = self.processor.process(key=Keys.RIGHT)
        self.assertEqual(1, self.state.keyboard_tab)
        self.assertTrue(event.prevent_key_process, "the arrow must be swallowed")
        self.processor.process(key=Keys.LEFT)
        self.assertEqual(0, self.state.keyboard_tab)

    def test_the_tabs_wrap_in_both_directions(self):
        self.processor.process(key=Keys.LEFT)
        self.assertEqual(len(TABS) - 1, self.state.keyboard_tab)
        self.processor.process(key=Keys.RIGHT)
        self.assertEqual(0, self.state.keyboard_tab)

    def test_arrows_are_left_alone_when_the_sheet_is_closed(self):
        self.state.keyboard_active = False
        self.processor.process(key=Keys.RIGHT)
        self.assertEqual(0, self.state.keyboard_tab)

    def test_closing_returns_to_the_first_tab(self):
        self.processor.process(key=Keys.RIGHT)
        self.processor.process(key=Keys.ESC)
        self.assertFalse(self.state.keyboard_active)
        self.assertEqual(0, self.state.keyboard_tab)


class TestAppWiring(unittest.TestCase):
    def test_show_and_hide_run_on_the_worker_thread(self):
        calls = []
        caller = threading.current_thread()

        def record(name):
            def inner(*args):
                calls.append((name, threading.current_thread()))

            return inner

        config = Config.from_file(CONFIG_PATH)
        listener = ScriptedListener(
            [
                (config.special_key, "d"),
                (config.keyboard_key, "d"),
                (config.keyboard_key, "u"),
                (config.special_key, "u"),
                (Keys.ESC, "d"),
            ]
        )
        app = App(
            config_path=CONFIG_PATH,
            mouse_config_path=MOUSE_CONFIG_PATH,
            listener=listener,
            tray_app_interface=TrayAppInterface(set_icon=lambda *a: None, stop=None),
            keyboard_interface=KeyboardInterface(
                show=record("show"), hide=record("hide")
            ),
        )
        app.main()
        app.worker.join(timeout=5)

        names = [name for name, _ in calls]
        self.assertIn("show", names)
        self.assertIn("hide", names)
        first_show = names.index("show")
        last_hide = len(names) - 1 - names[::-1].index("hide")
        self.assertLess(first_show, last_hide, "ESC should have closed it again")
        for name, thread in calls:
            self.assertIsNot(thread, caller, f"{name} ran on the listener thread")


class TestRendering(unittest.TestCase):
    """The drawing itself, when a display is available (WSLg counts)."""

    def setUp(self):
        tk = self.tk = __import__("tkinter")
        try:
            root = tk.Tk()
        except Exception as error:  # no display, no Tk build
            raise unittest.SkipTest(f"no usable display: {error}")
        root.destroy()

    def test_it_draws_the_real_config_without_error(self):
        from app.keyboard_layout import build
        from os_level.keyboard_window import KeyboardWindow

        config = Config.from_file(CONFIG_PATH)
        window = KeyboardWindow(lambda tab: build(config, tab), overlay=False)
        window.show()
        self.assertTrue(window.is_visible)
        self.assertIsNotNone(window.root)
        window.clear()
        self.assertFalse(window.is_visible)
        window.clear()  # closing twice must stay harmless

    def test_it_draws_every_tab_and_steps_between_them(self):
        from app.keyboard_layout import build
        from os_level.keyboard_window import KeyboardWindow

        config = Config.from_file(CONFIG_PATH)
        window = KeyboardWindow(lambda tab: build(config, tab), overlay=False)
        try:
            for tab in TABS:
                window.show(tab)
                self.assertEqual(tab, window.tab)
            window.step(1)
            self.assertEqual(TABS[0], window.tab, "stepping past the end wraps")
            window.step(-1)
            self.assertEqual(TABS[-1], window.tab)
        finally:
            window.clear()

    def test_stepping_while_closed_does_nothing(self):
        from app.keyboard_layout import build
        from os_level.keyboard_window import KeyboardWindow

        config = Config.from_file(CONFIG_PATH)
        window = KeyboardWindow(lambda tab: build(config, tab), overlay=False)
        window.step(1)
        self.assertFalse(window.is_visible)


if __name__ == "__main__":
    unittest.main()
