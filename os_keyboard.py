from app.enums import Keys, keyboard_to_dokey_map
import keyboard  # third party


def read_event() -> (Keys, bool, str):
    """Keyboard third part read event.

    shift+k returned as K (uppercase)
    """
    event = keyboard.read_event(suppress=True)
    event_name: str = event.name
    if event_name == "D":
        print("wft!")
    key = keyboard_to_dokey_map.get(event_name.lower(), event.name)
    if not isinstance(key, Keys):
        print("MISSING EVENT", event.name)
        key = Keys.NONE

    is_up = event.event_type == "up"

    # passthrough method with params baked in
    def func_pass():
        if event_name == "D":
            print("Send capital D. Mute sound on windows??????")
        return keyboard.send(event.name, do_press=not is_up, do_release=is_up)

    return key, is_up, func_pass


def keyboard_send(send_keyboard):
    keyboard.send(send_keyboard)
