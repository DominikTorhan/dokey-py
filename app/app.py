import subprocess
import os
from abc import ABC, abstractmethod
from typing import List
from app.app_state import AppState, OFF, NORMAL
from app.key_processor import Processor, Result
from app.config import Config
from app.input_key import InputKey
from app.enums import Keys, keys_to_send
from app.modificators import Modificators


class TrayAppInterface:
    def __init__(self, set_icon, stop):
        self.set_icon = set_icon
        self.stop = stop


class ListenerABC(ABC):
    @abstractmethod
    def run(self, func):
        # starts listener
        # func signature Keys, bool -> str, bool
        pass


class App:
    def __init__(
        self,
        config_path,
        listener: ListenerABC,
        tray_app_interface: TrayAppInterface = None,
    ):
        self.config = Config.from_file(config_path)
        self.listener = listener
        self.tray_app_interface = tray_app_interface
        self.app_state = AppState()
        self.is_sending = False

    def main(self):

        print("start main loop")
        self.listener.run(self.iteration)
        print("Terminate!")

    def process(self, key: Keys, is_up: bool, modifs_os: Modificators = None) -> Result:
        input_key = InputKey.from_string(key)
        processor = Processor()
        processor.config = self.config
        processor.app_state = self.app_state
        processor.input_key = input_key
        processor.is_key_up = is_up
        return processor.process(modifs_os=modifs_os)

    def iteration(self, key: Keys, is_up: bool, modifs_os: Modificators = None):
        # key, is_up, pass_func = self.keyboard_interface.wait_for_keyboard()
        # if self.is_sending: # TODO: send in implementation?
        #     return None, False
        print("new event:", key, "is_up: ", is_up)
        result = self.process(key, is_up, modifs_os)
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
                return send, True  # TODO: EXit
            prevent = result.prevent_key_process
            is_sending = True
            if result.cmd:
                cmd = result.cmd
                print(f"EXEC {cmd}")
                os.popen(cmd)  # popen for proper thread/subprocess
            elif send and len(send) > 0:
                send_keyboard = keys_to_send(send)
                print(send, " -> ", send_keyboard)
                # if there is send, there will be always PREV
                return send, True
                # self.keyboard_interface.send_keyboard_event(send_keyboard)
        is_sending = False
        return None, prevent
