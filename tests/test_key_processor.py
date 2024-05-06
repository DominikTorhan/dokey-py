import unittest
from pathlib import Path
import yaml
from app.app_state import AppState
from app.events import SendEvent, CMDEvent, WriteEvent
from app.key_processor import Event, KeyProcessor
from app.config import Config
from app.keys import Keys, string_to_multi_keys
from app.modifs import Modifs
from app.mouse_config import MouseConfig

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
MOUSE_CONFIG_PATH = Path(__file__).parent.parent / "app" / "mouse_config.yaml"
PLAYLIST_PATH = Path(__file__).parent / "test_playlist.yaml"


class TestPlaylist(unittest.TestCase):

    def setUp(self) -> None:

        with open(PLAYLIST_PATH, "r") as f:
            playlist_data: dict = yaml.safe_load(f)

        self.playlist_data = playlist_data["playlist"]

    def test_key_processor(self):
        config = Config.from_file(CONFIG_PATH)
        mouse_config = MouseConfig.from_file(CONFIG_PATH)
        state = AppState()
        processor = KeyProcessor(config, mouse_config, state)

        playlist = self.playlist_data

        i = 0

        for run in playlist:
            i += 1
            input = run["input"]
            expected = run["output"]

            inputs = input.split()

            app_state = AppState()
            strs = inputs[0].split(",")
            mode = int(strs[0])
            first_step = Keys.from_string(strs[1])

            modif_str = strs[2]
            modifs = Modifs()
            modifs.control = "^" in modif_str
            modifs.shift = "+" in modif_str
            modifs.alt = "%" in modif_str
            modifs.win = "w" in modif_str
            app_state.modifs = modifs

            prevent_prev_mode_on_special_up = "*" in strs[2]

            key = Keys.from_string(inputs[1])
            is_up = inputs[2] == "up"

            state.mode = mode
            state.first_step = first_step
            state.modifs = modifs
            state.prevent_prev_mode_on_special_up = prevent_prev_mode_on_special_up
            state.is_special_down = "s" in modif_str

            if input == "1,,s a down":
                x = 0

            # main call
            event = processor.process(key=key, is_key_up=is_up)

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
            modifs = strs[2]
            is_special_down = False
            if "s" in modifs:
                is_special_down = True
                modifs = modifs.replace("s", "")

            prevent_prev_mode_on_special_up = "*" in strs[3]

            send = []
            if strs[4]:
                send = string_to_multi_keys(strs[4])
            prevent_key_process = "PREV" in strs[5]

            self.assertEqual(mode, state.mode)
            self.assertEqual(first_step, state.first_step)
            self.assertEqual(is_special_down, state.is_special_down)
            self.assertEqual(modifs, state.modifs.to_string())
            self.assertEqual(
                prevent_prev_mode_on_special_up, state.prevent_prev_mode_on_special_up
            )

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
