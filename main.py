from app.app import App
from app.enums import Keys, keyboard_to_dokey_map
from pathlib import Path

import keyboard  # third party


def read_event() -> (Keys, bool, str):
    """Keyboard third part read event.

    shift+k returned as K (uppercase)
    """
    event = keyboard.read_event(suppress=True)
    event_name: str = event.name
    key = keyboard_to_dokey_map.get(event_name.lower(), event.name)
    if not isinstance(key, Keys):
        print("MISSING EVENT", event.name)

    is_up = event.event_type == "up"

    # passthrough method with params baked in
    def func_pass():
        return keyboard.send(event.name, do_press=not is_up, do_release=is_up)

    return key, is_up, func_pass


def send_event_pass_though(keyboard_key: str, is_up: bool) -> None:
    keyboard.send(keyboard_key, do_press=not is_up, do_release=is_up)
    pass


def keyboard_send(send_keyboard):
    keyboard.send(send_keyboard)

# main entrypoint
if __name__ == "__main__":
    config_path = str(Path(__file__).parent / "app" / "config.yaml")
    app = App(read_event, keyboard_send, config_path)
    app.main()
