import logging
import os
import queue
import threading
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
        # Slow side effects run here instead of on the keyboard hook thread.
        self.side_effects: queue.Queue = queue.Queue()
        self.worker: threading.Thread = None

    def main(self):

        logger.info("Started DoKey App.")
        self.worker = threading.Thread(
            target=self._run_side_effects, name="dokey-side-effects", daemon=True
        )
        self.worker.start()
        try:
            self.listener.run(self.handle_keyboard_event)
        finally:
            self.side_effects.put(None)
        logger.info("Terminate!")

    def _run_side_effects(self):
        """Drain the queue fed by handle_keyboard_event. One thread, so overlay
        windows are always created and destroyed on the same thread."""
        while True:
            job = self.side_effects.get()
            if job is None:
                break
            try:
                job()
            except Exception:
                logger.exception("Side effect failed")

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

        if isinstance(event, SendEvent):
            pretty_send = keys_to_send(event.send)
            trigger_info = pretty_trigger(old_first_step, trigger.key)
            modifs_info = self.state.modifs.to_string()
            logger.info(f"SEND: {pretty_send} [{trigger_info}] {modifs_info}")

        if isinstance(event, DoKeyEvent):
            logger.info(f"DokeyEvent: {event.event_type}")
            if event.event_type == "exit":
                # done inline: there may be no worker left to run it
                if self.tray_app_interface:
                    self.tray_app_interface.stop()
                return event

        self._defer_side_effects(event)
        return event

    def _defer_side_effects(self, event: EventLike):
        """Hand the slow work to the worker thread.

        Creating an overlay window or spawning a command takes far longer than
        the LowLevelHooksTimeout Windows allows a hook callback (300 ms by
        default); overrunning it makes Windows silently drop the hook, leaving
        DoKey running but no longer remapping anything.

        The current state is snapshotted here rather than read in the job,
        because it keeps changing as further keys arrive.
        """
        mode = self.state.mode
        first_step = self.state.first_step
        is_help_down = self.state.is_help_down
        diagnostic_active = self.state.diagnostic_active
        cmd = event.cmd if isinstance(event, CMDEvent) else None
        clear_screen = (
            isinstance(event, DoKeyEvent) and event.event_type == "clear_screen"
        )

        has_ui = any(
            [
                self.tray_app_interface,
                self.help_interface,
                self.mouse_interface,
                self.diagnostics_interface,
            ]
        )
        if not has_ui and not cmd:
            return

        self.side_effects.put(
            lambda: self._apply_side_effects(
                mode, first_step, is_help_down, diagnostic_active, cmd, clear_screen
            )
        )

    def _apply_side_effects(
        self, mode, first_step, is_help_down, diagnostic_active, cmd, clear_screen
    ):
        if self.tray_app_interface:
            self.tray_app_interface.set_icon(mode, first_step)

        if self.help_interface:
            if is_help_down:
                self.help_interface.show()
            else:
                self.help_interface.hide()

        if self.mouse_interface:
            if mode == MOUSE:
                self.mouse_interface.show()
            else:
                self.mouse_interface.hide()

        if self.diagnostics_interface:
            if diagnostic_active:
                self.diagnostics_interface.show()
            else:
                self.diagnostics_interface.hide()

        if clear_screen and self.mouse_interface:
            self.mouse_interface.clear()

        # Execute custom command
        if cmd:
            logger.info(f"EXEC CMD: {cmd}")
            # TODO: this is potential security breach
            os.popen(cmd)  # popen for proper thread/subprocess
