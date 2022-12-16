import unittest
from pathlib import Path
import yaml
from app.input_key import InputKey
from app.app_state import AppState
from app.key_processor import Result, Processor
from app.config import Config
from app.enums import Keys, keys_to_send
from app.modificators import Modificators
from main import App, ListenerABC

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"
PLAYLIST_PATH = Path(__file__).parent / "test_playlist.yaml"




class TestPlaylist(unittest.TestCase):
    def manage_input(self, string: str) -> (AppState, str, bool):
        strs = string.split()
        app_state = self.app_state_from_string(strs[0])
        key = Keys.from_string(strs[1])
        is_up = strs[2] == "up"
        return app_state, key, is_up

    def app_state_from_string(self, string: str) -> AppState:
        """0,,
        1,i,^+%wc*
        """
        app_state = AppState()
        strs = string.split(",")
        app_state.state = int(strs[0])
        app_state.first_step = Keys.from_string(strs[1])
        app_state.modificators = self.modificators_from_string(strs[2])
        app_state.prevent_esc_on_caps_up = "*" in strs[2]
        return app_state

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
        string += result.app_state.to_string()
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

    def main(self, key: str, app_state: AppState, config: Config, is_up: bool) -> Result:

        input_key = InputKey.from_string(key)
        processor = Processor()
        processor.config = config
        processor.app_state = app_state
        processor.input_key = input_key
        processor.is_key_up = is_up
        result = processor.process()
        return result

    def test_playlist(self):
        config = Config.from_file(CONFIG_PATH)
        playlist = self.read_playlist()

        i = 0

        for run in playlist:
            i += 1
            input = run["input"]
            expected = run["output"]
            print(input, expected)
            app_state, key, is_up = self.manage_input(input)
            # main call
            result = self.main(key, app_state, config, is_up)
            actual = self.result_to_string(result)

            self.assertEqual(actual, expected)



if __name__ == '__main__':
    unittest.main()