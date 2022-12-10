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
from main import App, ListenerABC


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
            # (Keys.CAPS, "d"),
            # (Keys.F, "d"),
            # (Keys.F, "u"),
            # (Keys.CAPS, "u"),
            (Keys.J, "d"),
            (Keys.CAPS, "d"),
            (Keys.F, "d"),
            (Keys.F, "u"),
            (Keys.CAPS, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"),
            (Keys.CAPS, "d"),
            (Keys.BACKSPACE, "d"),  # caps+backspace - exit app
        ],
        ["down"],
    ),
    (
        [
            # (Keys.CAPS, "d"),
            # (Keys.F, "d"),  # state 1
            # (Keys.F, "u"),
            (Keys.CAPS, "d"),
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
            (Keys.F, "d"),  # state 2
            (Keys.F, "u"),
            (Keys.T, "d"),  # caps+t = Tab
            (Keys.T, "u"),
            (Keys.CAPS, "u"),  # prevent caps on up (otherwise would change the state)
            (Keys.Z, "d"),  # nothing (insert mode)
            (Keys.Z, "u"),
            (Keys.CAPS, "d"),
            (Keys.CAPS, "u"),  # state 1
            (Keys.COMMA, "d"),  # page up
            (Keys.COMMA, "u"),
            (Keys.D, "d"),  # first step d
            (Keys.D, "u"),
            (Keys.Z, "d"),  # dz -> ctrl+f7,ctrl+f8 (evernote trick)
            (Keys.Z, "u"),
            (Keys.CAPS, "d"),
            (Keys.BACKSPACE, "d"),  # caps+backspace - exit app
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
        while(True):
            key, up = next(gen_read)
            is_up = up == "u"
            send, prev = func(key, is_up)
            if send and len(send) > 0:
                if Keys.COMMAND_EXIT in send:
                    break
                expected = next(gen_send)
                send_keyboard = keys_to_send(send)
                print(f"send {send_keyboard} (expected: {expected})")
                assert send_keyboard == expected


def test_app():
    def test_run(events, sends):
        listener = TestListener(events, sends)

        app = App(CONFIG_PATH, listener)
        app.main()

    for test in test_app_playlist:
        test_run(test[0], test[1])


if __name__ == "__main__":
    test_app()
    test_playlist()
    print("ALL GOOD!!!")
