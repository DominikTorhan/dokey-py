import unittest
from pathlib import Path
import yaml
from app.app_state import AppState
from app.key_processor import Result, KeyProcessor
from app.config import Config
from app.keys import Keys, keys_to_send
from app.modificators import Modificators

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
PLAYLIST_PATH = Path(__file__).parent / "test_playlist.yaml"


class TestPlaylist(unittest.TestCase):
    def manage_input(self, string: str) -> (AppState, str, bool):
        strs = string.split()
        app_state, state = self.app_state_from_string(strs[0])
        key = Keys.from_string(strs[1])
        is_up = strs[2] == "up"
        return app_state, key, is_up, state

    def app_state_from_string(self, string: str) -> (AppState, int):
        """0,,
        1,i,^+%wc*
        """
        app_state = AppState()
        strs = string.split(",")
        state = int(strs[0])
        app_state.first_step = Keys.from_string(strs[1])
        app_state.modificators = self.modificators_from_string(strs[2])
        app_state.prevent_esc_on_caps_up = "*" in strs[2]
        return app_state, state

    def modificators_from_string(self, string) -> Modificators:
        modificators = Modificators()
        modificators.control = "^" in string
        modificators.shift = "+" in string
        modificators.alt = "%" in string
        modificators.win = "w" in string
        modificators.caps = "c" in string
        return modificators

    def result_to_string(self, result: Result) -> str:
        if not result:
            return "None"
        string = ""
        string += result.app_state.to_string(result.state)
        string += " "
        if result.send:
            string += keys_to_send(result.send)
        else:
            string += "nil"
        if result.prevent_key_process:
            string += " PREV"
        return string

    def read_playlist(self) -> list:
        with open(PLAYLIST_PATH, "r") as f:
            playlist_data: dict = yaml.safe_load(f)

        return playlist_data["playlist"]

    def test_key_processor(self):
        config = Config.from_file(CONFIG_PATH)
        processor = KeyProcessor()
        processor.config = config

        playlist = self.read_playlist()

        i = 0

        for run in playlist:
            i += 1
            input = run["input"]
            expected = run["output"]
            app_state, key, is_up, state = self.manage_input(input)
            # main call
            processor.app_state = app_state
            #state = app_state.state
            if i == 23:
                x = 0
            try:
                result = processor.process(key=key, state=state, is_key_up=is_up)
            except:
                x = 0

            actual = self.result_to_string(result)

            if expected != actual:
                x = 0

            self.assertEqual(expected, actual)
