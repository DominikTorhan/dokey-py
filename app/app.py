from typing import Callable, Any, List
import logging
import os
from abc import ABC, abstractmethod
from app.app_state import AppState, OFF, NORMAL
from app.events import Event, SendEvent, CMDEvent, DoKeyEvent, EventLike
from app.key_processor import KeyProcessor
from app.config import Config
from app.keys import Keys, keys_to_send, pretty_trigger
from app.modificators import Modificators


logger = logging.getLogger(__name__)


class TrayAppInterface:
    def __init__(self, set_icon, stop):
        self.set_icon = set_icon
        self.stop = stop


class OSEvent:
    def __init__(self):
        self.key: Keys = Keys.NONE
        self.is_key_up: bool = False
        self.modifs_os: Modificators = Modificators()


class ListenerABC(ABC):
    @abstractmethod
    def run(self, func: Callable[[OSEvent], EventLike]):
        # starts listener
        pass


class App:
    def __init__(
        self,
        config_path,
        listener: ListenerABC,
        tray_app_interface: TrayAppInterface = None,
    ):
        self.config: Config = Config.from_file(config_path)
        self.listener: ListenerABC = listener
        self.tray_app_interface: TrayAppInterface = tray_app_interface
        self.state = AppState()
        self.state.mode = NORMAL
        self.processor: KeyProcessor = KeyProcessor(self.config, self.state)

    def main(self):

        logger.info("Started DoKey App.")
        self.listener.run(self.handle_keyboard_event)
        logger.info("Terminate!")

    def handle_keyboard_event(self, trigger: OSEvent) -> EventLike:
        """Main function to handle keyboard event. It is a kind of iteration in the main while loop."""
        logger.debug(
            f"EVENT: {trigger.key}, vk{str(trigger.key.value)} {'up' if trigger.is_key_up else 'down'}"
        )

        old_mode = self.state.mode
        old_first_step = self.state.first_step

        # process changes the app state
        event = self.processor.process(
            key=trigger.key,
            is_key_up=trigger.is_key_up,
            modifs_os=trigger.modifs_os,
        )
        if not event:
            return Event()

        if self.tray_app_interface:
            self.tray_app_interface.set_icon(self.state.mode, self.state.first_step)

        if isinstance(event, DoKeyEvent):
            # Only one DoKeyEvent for now. Exit command
            if self.tray_app_interface:
                self.tray_app_interface.stop()

        if isinstance(event, SendEvent):
            pretty_send = keys_to_send(event.send)
            trigger_info = pretty_trigger(old_first_step, trigger.key)
            modifs_info = self.state.modificators.to_string()
            logger.info(
                f"SEND: {pretty_send} [{(trigger_info)}] {modifs_info}"
            )

        # Execute custom command
        if isinstance(event, CMDEvent):
            cmd = event.cmd
            logger.info(f"EXEC CMD: {cmd}")
            os.popen(cmd)  # popen for proper thread/subprocess

        return event
