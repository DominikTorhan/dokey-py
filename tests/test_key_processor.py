import unittest
from pathlib import Path
import yaml
from app.current_state import CurrentState
from app.key_processor import Result, KeyProcessor
from app.config import Config
from app.keys import Keys, keys_to_send
from app.modificators import Modificators

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
PLAYLIST_PATH = Path(__file__).parent / "test_playlist.yaml"


class TestPlaylist(unittest.TestCase):

    def setUp(self) -> None:

        with open(PLAYLIST_PATH, "r") as f:
            playlist_data: dict = yaml.safe_load(f)

        self.playlist_data = playlist_data["playlist"]

    def result_to_string(self, result: Result) -> str:
        if not result:
            return "None"
        string = ""

        prev = "*" if result.prevent_esc_on_caps_up else ""

        s = f"{str(result.mode)},{result.first_step.to_string()},{result.modificators.to_string()}{prev}"
        # result.app_state.to_string(result.state, result.first_step)
        string += s
        string += " "
        if result.send:
            string += keys_to_send(result.send)
        else:
            string += "nil"
        if result.prevent_key_process:
            string += " PREV"
        return string

    def test_key_processor(self):
        config = Config.from_file(CONFIG_PATH)
        processor = KeyProcessor(config)

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

            # main call
            processor.app_state = app_state
            if i == 1:
                x = 0
            try:
                result = processor.process(
                    key=key,
                    is_key_up=is_up,
                    mode=mode,
                    first_step=first_step,
                    prevent_esc_on_caps_up=prevent_esc_on_caps_up,
                )
            except:
                x = 0

            actual = self.result_to_string(result)

            if expected != actual:
                x = 0

            self.assertEqual(expected, actual)
