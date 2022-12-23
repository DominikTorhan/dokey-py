from typing import Callable, Any, List
import logging
import os
from abc import ABC, abstractmethod
from app.current_state import CurrentState, OFF, NORMAL
from app.events import Event, SendEvent, CMDEvent, DoKeyEvent
from app.key_processor import KeyProcessor
from app.config import Config
from app.keys import Keys, keys_to_send
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
    def run(self, func: Callable[[OSEvent], Any]):
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
        self.state = CurrentState()
        self.state.mode = NORMAL
        self.processor: KeyProcessor = KeyProcessor(self.config, self.state)

    def main(self):

        logger.info("Started DoKey App.")
        self.listener.run(self.handle_keyboard_event)
        logger.info("Terminate!")

    def handle_keyboard_event(self, trigger: OSEvent) -> Event:
        """Main function to handle keyboard event. It is kind of iteration in main while loop."""
        logger.debug(
            f"EVENT: {trigger.key}, vk{str(trigger.key.value)} {'up' if trigger.is_key_up else 'down'}"
        )

        event = self.processor.process(
            key=trigger.key,
            is_key_up=trigger.is_key_up,
            modifs_os=trigger.modifs_os,
        )
        if not event:
            return Event()

        if self.tray_app_interface:
            self.tray_app_interface.set_icon(self.state.mode)

        if isinstance(event, DoKeyEvent):
            if self.tray_app_interface:
                self.tray_app_interface.stop()

        if isinstance(event, SendEvent):
            friendly_keys = keys_to_send(event.send)
            logger.info(f"SEND: {friendly_keys}")  # TODO: add trigger (eg. f,f -> f12)
            # terminate app
            # if Keys.COMMAND_EXIT in event.send: # TODO
            #     if self.tray_app_interface:
            #         self.tray_app_interface.stop()
            #return event

        # Execute custom command
        if isinstance(event, CMDEvent):
            cmd = event.cmd
            logger.info(f"EXEC CMD: {cmd}")
            os.popen(cmd)  # popen for proper thread/subprocess

        return event
