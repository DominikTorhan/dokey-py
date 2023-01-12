import unittest
from pathlib import Path

from app.app import OSEvent, ListenerABC
from app.events import SendEvent, DoKeyEvent, EventLike
from app.keys import Keys, keys_to_send
from main import App

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
MOUSE_CONFIG_PATH = Path(__file__).parent.parent / "app" / "mouse_config.yaml"

EXIT_KEY = Keys.PRINT_SCREEN

test_app_playlist = [
    (
        [
            (Keys.J, "d"),
            (Keys.CAPS, "d"),
            (Keys.F, "d"),
            (Keys.F, "u"),
            (Keys.CAPS, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"),
            (Keys.CAPS, "d"),
            (EXIT_KEY, "d"),  # caps+backspace - exit app
        ],
        ["down"],
    ),
    (
        [
            (Keys.CAPS, "d"),
            (Keys.R, "d"),
            (Keys.R, "u"),
            (Keys.CAPS, "u"),
            (Keys.Z, "d"),
            (Keys.Z, "u"),
            (Keys.I, "d"),  # first step
            (Keys.I, "u"),
            (Keys.K, "d"),
            (Keys.K, "u"),
            (Keys.CAPS, "d"),
            (Keys.F, "d"),  # mode 2
            (Keys.F, "u"),
            (Keys.T, "d"),  # caps+t = Tab
            (Keys.T, "u"),
            (Keys.CAPS, "u"),  # prevent caps on up (otherwise would change the state)
            (Keys.Z, "d"),  # nothing (insert mode)
            (Keys.Z, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"),  # mode 1
            (Keys.COMMA, "d"),  # page up
            (Keys.COMMA, "u"),
            (Keys.D, "d"),  # first step d
            (Keys.D, "u"),
            (Keys.Z, "d"),  # dz -> ctrl+f7,ctrl+f8 (evernote trick)
            (Keys.Z, "u"),
            (Keys.CAPS, "d"),
            (EXIT_KEY, "d"),  # caps+backspace - exit app
        ],
        ["enter", "ctrl+z", "up,end,enter", "tab", "page up", "ctrl+f7,ctrl+f8"],
    ),
]


class TestListener(ListenerABC):
    def __init__(self, events, sends):
        self.events = events
        self.sends = sends

    def run(self, func):
        gen_read = iter(self.events)
        gen_send = iter(self.sends)
        while True:
            key, up = next(gen_read)
            is_up = up == "u"
            trigger = OSEvent()
            trigger.key = key
            trigger.is_key_up = is_up
            event: EventLike = func(trigger)
            if isinstance(event, DoKeyEvent):
                # exit
                break
            if isinstance(event, SendEvent):
                # if Keys.COMMAND_EXIT in event.send:
                #     break
                expected = next(gen_send)
                send_keyboard = keys_to_send(event.send)
                # print(f"send {send_keyboard} (expected: {expected})")
                assert send_keyboard == expected


class TestApp(unittest.TestCase):
    def test_app(self):
        def test_run(events, sends):
            listener = TestListener(events, sends)

            app = App(
                config_path=CONFIG_PATH,
                mouse_config_path=MOUSE_CONFIG_PATH,
                listener=listener,
            )
            app.main()

        for test in test_app_playlist:
            # check if doesn't crash
            test_run(test[0], test[1])
