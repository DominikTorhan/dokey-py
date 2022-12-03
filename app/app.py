from typing import List
from app.app_state import AppState
from app.key_processor import Processor, Result
from app.config import Config
from app.input_key import InputKey
from app.enums import Keys, keys_to_send


class KeyboardInterface:
    def __init__(self, wait_for_keyboard, send_keyboard_event):
        self.wait_for_keyboard = wait_for_keyboard
        self.send_keyboard_event = send_keyboard_event


class TrayAppInterface:
    def __init__(self, set_icon, stop):
        self.set_icon = set_icon
        self.stop = stop


class App:
    def __init__(
        self,
        config_path,
        keyboard_interface: KeyboardInterface,
        tray_app_interface: TrayAppInterface = None,
    ):
        self.config = Config.from_file(config_path)
        self.keyboard_interface = keyboard_interface
        self.tray_app_interface = tray_app_interface
        self.app_state = AppState()

    def main(self):
        def process(key: Keys, is_up: bool) -> Result:
            input_key = InputKey.from_string(key)
            processor = Processor()
            processor.config = self.config
            processor.app_state = self.app_state
            processor.input_key = input_key
            processor.is_key_up = is_up
            return processor.process()

        is_sending = False

        # main loop
        while True:
            key, is_up, pass_func = self.keyboard_interface.wait_for_keyboard()
            if is_sending:
                continue
            print("new event:", key, "is_up: ", is_up)
            result = process(key, is_up)
            prevent = False
            if result:
                state_changed = self.app_state.state != result.app_state.state
                self.app_state = result.app_state
                if state_changed and self.tray_app_interface:
                    self.tray_app_interface.set_icon(self.app_state.state)
                print("new state: ", self.app_state.to_string())
                send: List[Keys] = result.send
                if Keys.COMMAND_EXIT in send:
                    print("EXEC EXIT COMMAND!")
                    if self.tray_app_interface:
                        self.tray_app_interface.stop()
                    break
                is_sending = True
                prevent = result.prevent_key_process
                if send:
                    send_keyboard = keys_to_send(send)
                    print(send, " -> ", send_keyboard)
                    self.keyboard_interface.send_keyboard_event(send_keyboard)
            is_sending = False
            if not prevent:
                pass_func()

        print("Terminate!")
