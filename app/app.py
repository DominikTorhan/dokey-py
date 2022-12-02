from typing import List
from app.app_state import AppState
from app.key_processor import Processor, Result
from app.config import Config
from app.input_key import InputKey
from app.enums import Keys, keys_to_send


class App:
    def __init__(self, func_read_event, func_send, config_path):
        self.func_sys_read_event = func_read_event
        self.func_sys_send = func_send
        self.config = Config.from_file(config_path)
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
            key, is_up, pass_func = self.func_sys_read_event()
            if is_sending:
                continue
            print("new event:", key, "is_up: ", is_up)
            result = process(key, is_up)
            prevent = False
            if result:
                self.app_state = result.app_state
                print("new state: ", self.app_state.to_string())
                send: List[Keys] = result.send
                if Keys.COMMAND_EXIT in send:
                    print("EXEC EXIT COMMAND!")
                    break
                is_sending = True
                prevent = result.prevent_key_process
                if send:
                    send_keyboard = keys_to_send(send)
                    print(send, " -> ", send_keyboard)
                    self.func_sys_send(send_keyboard)
            is_sending = False
            if not prevent:
                pass_func()

        print("Terminate!")
