# //Test strategy:
# //	Config
# //	AppState
# //	KeyEvent (key and isUp)
# //	Result (AppState, send, preventKeyProcess)
#
# //everything in two strings (Input and Output):
# //Input:{appState} {key} {isUp} Output:{appState} {send} {preventKeyProcess}
# //		0,,c f down					   1,,c* ? ?
# //		1,f,^ p up					   1,,^ ? ?
#
import yaml
from app.input_key import InputKey
from app.app_state import AppState
from app.key_processor import Result, Processor
from app.config import Config
from app.enums import Keys, keys_to_send
from app.modificators import Modificators
from main import App


CONFIG_PATH = "../app/config.yaml"


def manage_input(string: str) -> (AppState, str, bool):
    strs = string.split()
    app_state = app_state_from_string(strs[0])
    key = Keys.from_string(strs[1])
    is_up = strs[2] == "up"
    return app_state, key, is_up


def app_state_from_string(string: str) -> AppState:
    """0,,
    1,i,^+%wc*
    """
    app_state = AppState()
    strs = string.split(",")
    app_state.state = int(strs[0])
    app_state.first_step = Keys.from_string(strs[1])
    app_state.modificators = modificators_from_string(strs[2])
    app_state.prevent_esc_on_caps_up = "*" in strs[2]
    return app_state

def modificators_from_string(string) -> Modificators:
    modificators = Modificators()
    modificators.control = "^" in string
    modificators.shift = "+" in string
    modificators.alt = "%" in string
    modificators.win = "w" in string
    modificators.caps = "c" in string
    return modificators



def result_to_string(result: Result) -> str:
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


class TestRun:
    def __init__(self):
        self.input = ""
        self.output = ""


def read_playlist() -> list:
    path = "test_playlist.yaml"
    with open(path, "r") as f:
        playlist_data: dict = yaml.safe_load(f)

    return playlist_data["playlist"]


def main(key: str, app_state: AppState, config: Config, is_up: bool) -> Result:

    input_key = InputKey.from_string(key)
    processor = Processor()
    processor.config = config
    processor.app_state = app_state
    processor.input_key = input_key
    processor.is_key_up = is_up
    result = processor.process()
    return result


def test_playlist():
    config = Config.from_file(CONFIG_PATH)
    playlist = read_playlist()

    i = 0

    for run in playlist:
        i += 1
        input = run["input"]
        expected = run["output"]
        print(input, expected)
        app_state, key, is_up = manage_input(input)
        # main call
        result = main(key, app_state, config, is_up)
        actual = result_to_string(result)
        print("Actual:", actual)
        print("Expected:", expected)
        passed = actual == expected
        if not passed:
            print(f"{i} ERROR")
            raise AssertionError


test_app_playlist = [
    (
        [
            (Keys.CAPS, "d"),
            (Keys.F, "d"),
            (Keys.F, "u"),
            (Keys.CAPS, "u"),
            (Keys.J, "d"),
            (Keys.CAPS, "d"),
            (Keys.F, "d"),
            (Keys.F, "u"),
            (Keys.CAPS, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"),
            (Keys.COMMAND_EXIT, "d"),
        ],
        ["down"],
    ),
    (
        [
            (Keys.CAPS, "d"),
            (Keys.F, "d"), # state 1
            (Keys.F, "u"),
            (Keys.R, "d"),
            (Keys.R, "u"),
            (Keys.CAPS, "u"),
            (Keys.Z, "d"),
            (Keys.Z, "u"),
            (Keys.I, "d"),
            (Keys.I, "u"),
            (Keys.K, "d"),
            (Keys.K, "u"),
            (Keys.CAPS, "d"),
            (Keys.F, "d"), # state 2
            (Keys.F, "u"),
            (Keys.T, "d"), # caps+t = Tab
            (Keys.T, "u"),
            (Keys.CAPS, "u"), # prevent caps on up (otherwise would change the state)
            (Keys.Z, "d"), # nothing (insert mode)
            (Keys.Z, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"), # state 1
            (Keys.COMMA, "d"), # page up
            (Keys.COMMA, "u"),
            (Keys.COMMAND_EXIT, "d"),
        ],
        ["enter", "ctrl+z", "up,end,enter", "tab", "page up"],
    ),
]


def test_app():
    def test_run(events, sends):
        gen_read = iter(events)
        gen_send = iter(sends)

        def read_event():
            key, up = next(gen_read)
            is_up = up == "u"
            return key, is_up, send_pass

        def send_pass():
            print("send_pass!")

        def send(send):
            expected = next(gen_send)
            print(f"send {send} (expected: {expected})")
            assert send == expected

        app = App(read_event, send, CONFIG_PATH)
        app.main()

    for test in test_app_playlist:
        test_run(test[0], test[1])


if __name__ == "__main__":
    test_app()
    test_playlist()