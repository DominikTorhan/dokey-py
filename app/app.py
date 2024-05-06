import logging
import os
from abc import ABC, abstractmethod
from typing import Callable

from app.app_state import AppState, NORMAL, MOUSE
from app.config import Config
from app.events import Event, SendEvent, CMDEvent, DoKeyEvent, EventLike
from app.key_processor import KeyProcessor
from app.keys import Keys, keys_to_send, pretty_trigger
from app.modifs import Modifs
from app.mouse_config import MouseConfig

logger = logging.getLogger(__name__)


class TrayAppInterface:
    def __init__(self, set_icon, stop):
        self.set_icon = set_icon
        self.stop = stop


class HelpInterface:
    def __init__(self, show, hide):
        self.show = show
        self.hide = hide


class MouseInterface:
    def __init__(self, show, hide, clear):
        self.show = show
        self.hide = hide
        self.clear = clear


class DiagnosticsInterface:
    def __init__(self, show, hide):
        self.show = show
        self.hide = hide


class OSEvent:
    def __init__(self):
        self.key: Keys = Keys.NONE
        self.is_key_up: bool = False
        self.modifs_os: Modifs = Modifs()


class ListenerABC(ABC):
    @abstractmethod
    def run(self, func: Callable[[OSEvent], EventLike]):
        # starts listener
        pass


class App:
    def __init__(
        self,
        config_path,
        mouse_config_path,
        listener: ListenerABC,
        tray_app_interface: TrayAppInterface = None,
        help_interface: HelpInterface = None,
        mouse_interface: MouseInterface = None,
        diagnostics_interface: DiagnosticsInterface = None,
    ):
        self.config: Config = Config.from_file(config_path)
        self.mouse_config: MouseConfig = MouseConfig.from_file(mouse_config_path)
        self.listener: ListenerABC = listener
        self.tray_app_interface: TrayAppInterface = tray_app_interface
        self.help_interface: HelpInterface = help_interface
        self.mouse_interface = mouse_interface
        self.diagnostics_interface = diagnostics_interface
        self.state = AppState()
        self.state.mode = NORMAL
        self.processor: KeyProcessor = KeyProcessor(
            self.config, self.mouse_config, self.state
        )

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

        if self.help_interface:
            if self.state.is_help_down:
                self.help_interface.show()
            else:
                self.help_interface.hide()

        if self.mouse_interface:
            if self.state.mode == MOUSE:
                self.mouse_interface.show()
            else:
                self.mouse_interface.hide()

        if self.diagnostics_interface:
            if self.state.diagnostic_active:
                self.diagnostics_interface.show()
            else:
                self.diagnostics_interface.hide()

        if isinstance(event, DoKeyEvent):
            logger.info(f"DokeyEvent: {event.event_type}")
            if event.event_type == "exit":
                logger.info("debug1")
                if self.tray_app_interface:
                    self.tray_app_interface.stop()
            elif event.event_type == "clear_screen":
                logger.info("debug2")
                if self.mouse_interface:
                    self.mouse_interface.clear()

        if isinstance(event, SendEvent):
            pretty_send = keys_to_send(event.send)
            trigger_info = pretty_trigger(old_first_step, trigger.key)
            modifs_info = self.state.modifs.to_string()
            logger.info(f"SEND: {pretty_send} [{trigger_info}] {modifs_info}")

        # Execute custom command
        if isinstance(event, CMDEvent):
            cmd = event.cmd
            logger.info(f"EXEC CMD: {cmd}")
            # TODO: this is potential security breach
            os.popen(cmd)  # popen for proper thread/subprocess

        return event
