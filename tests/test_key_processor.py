import unittest
from pathlib import Path
import yaml
from app.current_state import CurrentState
from app.events import SendEvent, CMDEvent, WriteEvent
from app.key_processor import Event, KeyProcessor
from app.config import Config
from app.keys import Keys, string_to_multi_keys
from app.modificators import Modificators

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
PLAYLIST_PATH = Path(__file__).parent / "test_playlist.yaml"


class TestPlaylist(unittest.TestCase):

    def setUp(self) -> None:

        with open(PLAYLIST_PATH, "r") as f:
            playlist_data: dict = yaml.safe_load(f)

        self.playlist_data = playlist_data["playlist"]

    def test_key_processor(self):
        config = Config.from_file(CONFIG_PATH)
        state = CurrentState()
        processor = KeyProcessor(config, state)

        playlist = self.playlist_data

        i = 0

        for run in playlist:
            i += 1
            input = run["input"]
            expected = run["output"]

            inputs = input.split()

            app_state = CurrentState()
            strs = inputs[0].split(",")
            mode = int(strs[0])
            first_step = Keys.from_string(strs[1])

            modif_str = strs[2]
            modificators = Modificators()
            modificators.control = "^" in modif_str
            modificators.shift = "+" in modif_str
            modificators.alt = "%" in modif_str
            modificators.win = "w" in modif_str
            modificators.caps = "c" in modif_str
            app_state.modificators = modificators

            prevent_esc_on_caps_up = "*" in strs[2]

            key = Keys.from_string(inputs[1])
            is_up = inputs[2] == "up"

            state.mode = mode
            state.first_step = first_step
            state.modificators = modificators
            state.prevent_esc_on_caps_up = prevent_esc_on_caps_up

            if input == "1,i, d2 down":
                x = 0

            # main call
            try:
                event = processor.process(
                    key=key,
                    is_key_up=is_up,
                )
            except:
                x = 0

            if not event:
                self.assertEqual(expected, "None")
                continue

            if isinstance(event, CMDEvent):
                self.assertEqual(1, state.mode)
                self.assertEqual(Keys.NONE, state.first_step)
                self.assertEqual(expected, event.cmd)
                continue
            if isinstance(event, WriteEvent):
                self.assertEqual(1, state.mode)
                self.assertEqual(Keys.NONE, state.first_step)
                self.assertEqual(expected, event.text)
                continue
            # 0||c|||PREV

            strs = expected.split("|")
            mode = int(strs[0])
            first_step = Keys.from_string(strs[1])
            modificators = strs[2]

            prevent_esc_on_caps_up = "*" in strs[3]

            send = []
            if strs[4]:
                send = string_to_multi_keys(strs[4])
            prevent_key_process = "PREV" in strs[5]

            self.assertEqual(mode, state.mode)
            self.assertEqual(first_step, state.first_step)
            self.assertEqual(modificators, state.modificators.to_string())
            self.assertEqual(prevent_esc_on_caps_up, state.prevent_esc_on_caps_up)

            actual_send = []
            actual_prevent_key_process = True
            if isinstance(event, SendEvent):
                actual_send = event.send
            if isinstance(event, Event):
                actual_prevent_key_process = event.prevent_key_process
            self.assertEqual(send, actual_send)
            actual_cmd = ""
            self.assertEqual("", actual_cmd)
            self.assertEqual(prevent_key_process, actual_prevent_key_process)
