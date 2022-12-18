import logging
import os
from abc import ABC, abstractmethod
from app.app_state import AppState, OFF, NORMAL
from app.key_processor import KeyProcessor, Result
from app.config import Config
from app.keys import Keys, keys_to_send
from app.modificators import Modificators


logger = logging.getLogger(__name__)


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
        self.processor = KeyProcessor()
        self.processor.config = self.config

    def main(self):

        logger.info("Started DoKey App.")
        self.listener.run(self.handle_keyboard_event)
        logger.info("Terminate!")

    def handle_keyboard_event(self, key: Keys, is_up: bool, modifs_os: Modificators = None):
        """Main function to handle keyboard event. It is kind of iteration in main while loop."""
        logger.info(f"EVENT: {key}, vk{str(key.value)} {'up' if is_up else 'down'}")

        self.processor.app_state = self.app_state
        result = self.processor.process(key=key, is_key_up=is_up, modifs_os=modifs_os)
        if not result:
            return None, False

        state_changed = self.app_state.state != result.app_state.state
        self.app_state = result.app_state
        if state_changed and self.tray_app_interface:
            self.tray_app_interface.set_icon(self.app_state.state)

        # terminate app
        if Keys.COMMAND_EXIT in result.send:
            if self.tray_app_interface:
                self.tray_app_interface.stop()
            return [Keys.COMMAND_EXIT], True  # TODO: EXit

        # Execute custom command
        if result.cmd:
            cmd = result.cmd
            logger.info(f"EXEC CMD: {cmd}")
            os.popen(cmd)  # popen for proper thread/subprocess
            return None, result.prevent_key_process

        if not result.send or len(result.send) == 0:
            return None, result.prevent_key_process

        send = result.send
        friendly_keys = keys_to_send(send)
        logger.info(f"SEND: {friendly_keys}") # TODO: add trigger (eg. f,f -> f12)
        return send, True
