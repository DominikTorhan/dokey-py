import threading
import unittest
from pathlib import Path

from app.app import App, HelpInterface, ListenerABC, OSEvent, TrayAppInterface
from app.keys import Keys

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
MOUSE_CONFIG_PATH = Path(__file__).parent.parent / "app" / "mouse_config.yaml"


class ScriptedListener(ListenerABC):
    """Replays key events on the calling thread, like the real keyboard hook."""

    def __init__(self, events):
        self.events = events
        self.returned = []

    def run(self, func):
        for key, direction in self.events:
            trigger = OSEvent()
            trigger.key = key
            trigger.is_key_up = direction == "u"
            self.returned.append(func(trigger))


class TestSideEffects(unittest.TestCase):
    """The keyboard hook callback must not do slow work: Windows drops a hook
    whose callback overruns LowLevelHooksTimeout."""

    def _run(self, events):
        self.calls = []
        caller = threading.current_thread()

        def record(name):
            def inner(*args):
                self.calls.append((name, threading.current_thread()))

            return inner

        tray = TrayAppInterface(set_icon=record("icon"), stop=record("stop"))
        help_interface = HelpInterface(show=record("show"), hide=record("hide"))
        listener = ScriptedListener(events)
        app = App(
            config_path=CONFIG_PATH,
            mouse_config_path=MOUSE_CONFIG_PATH,
            listener=listener,
            tray_app_interface=tray,
            help_interface=help_interface,
        )
        app.main()
        app.worker.join(timeout=5)
        self.assertFalse(app.worker.is_alive(), "side-effect worker did not finish")
        return caller, listener

    def test_ui_work_happens_off_the_listener_thread(self):
        caller, _ = self._run([(Keys.J, "d"), (Keys.J, "u"), (Keys.K, "d")])
        self.assertTrue(self.calls, "no side effects ran at all")
        for name, thread in self.calls:
            self.assertIsNot(thread, caller, f"{name} ran on the listener thread")

    def test_events_are_still_decided_synchronously(self):
        # suppression depends on the return value, so the decision cannot be
        # deferred even though its side effects are
        _, listener = self._run([(Keys.J, "d")])
        from app.events import SendEvent

        self.assertIsInstance(listener.returned[0], SendEvent)
        self.assertEqual([Keys.DOWN], listener.returned[0].send)
