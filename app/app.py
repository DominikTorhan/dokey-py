import logging
import queue
import subprocess
import threading
from abc import ABC, abstractmethod
from typing import Callable

from app.app_state import AppState, NORMAL, MOUSE
from app.config import Config
from app.events import Event, CMDEvent, DoKeyEvent, EventLike
from app.key_processor import KeyProcessor
from app.keyboard_layout import TABS
from app.keys import Keys
from app.modifs import Modifs
from app.mouse_config import MouseConfig
from app import usage

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


class KeyboardInterface:
    def __init__(self, show, hide):
        self.show = show
        self.hide = hide


class OSEvent:
    def __init__(self):
        self.key: Keys = Keys.NONE
        self.is_key_up: bool = False
        self.modifs_os: Modifs = Modifs()
        self.is_repeat: bool = False


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
        keyboard_interface: KeyboardInterface = None,
    ):
        self.config: Config = Config.from_file(config_path)
        self.mouse_config: MouseConfig = MouseConfig.from_file(mouse_config_path)
        self.listener: ListenerABC = listener
        self.tray_app_interface: TrayAppInterface = tray_app_interface
        self.help_interface: HelpInterface = help_interface
        self.mouse_interface = mouse_interface
        self.diagnostics_interface = diagnostics_interface
        self.keyboard_interface = keyboard_interface
        self.state = AppState()
        self.state.mode = NORMAL
        self.processor: KeyProcessor = KeyProcessor(
            self.config, self.mouse_config, self.state
        )
        # Slow side effects run here instead of on the keyboard hook thread.
        self.side_effects: queue.Queue = queue.Queue()
        self.worker: threading.Thread = None
        self._visible_overlays = {
            "help": False,
            "mouse": False,
            "diagnostics": False,
            "keyboard": False,
        }

    def main(self):

        logger.info("Started DoKey App.")
        fingerprint, bindings = usage.configuration(self.config, self.mouse_config)
        usage.record(
            "session_start",
            config=fingerprint,
            bindings=bindings,
            mode=self.state.mode,
            features={
                "help": self.help_interface is not None,
                "mouse_overlay": self.mouse_interface is not None,
                "diagnostics": self.diagnostics_interface is not None,
                "keyboard": self.keyboard_interface is not None,
            },
        )
        self.worker = threading.Thread(
            target=self._run_side_effects, name="dokey-side-effects", daemon=True
        )
        self.worker.start()
        try:
            self.listener.run(self.handle_keyboard_event)
        finally:
            self.side_effects.put(None)
            self.worker.join(timeout=5)
            usage.record("session_end", worker_drained=not self.worker.is_alive())
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

        old_mode = self.state.mode

        # process changes the app state
        event = self.processor.process(
            key=trigger.key,
            is_key_up=trigger.is_key_up,
            modifs_os=trigger.modifs_os,
        )
        if self.processor.binding_id and not trigger.is_key_up:
            usage.record(
                "binding",
                binding=self.processor.binding_id,
                action=self.processor.action,
                repeat=trigger.is_repeat,
                mode=old_mode,
                modifiers=self.state.modifs.to_string(),
            )
        if old_mode != self.state.mode:
            usage.record("mode", previous=old_mode, current=self.state.mode)
        if not event:
            return Event()

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
        keyboard_active = self.state.keyboard_active
        keyboard_tab = self.state.keyboard_tab
        cmd = event.cmd if isinstance(event, CMDEvent) else None
        binding = self.processor.binding_id
        clear_screen = (
            isinstance(event, DoKeyEvent) and event.event_type == "clear_screen"
        )

        has_ui = any(
            [
                self.tray_app_interface,
                self.help_interface,
                self.mouse_interface,
                self.diagnostics_interface,
                self.keyboard_interface,
            ]
        )
        if not has_ui and not cmd:
            return

        self.side_effects.put(
            lambda: self._apply_side_effects(
                mode,
                first_step,
                is_help_down,
                diagnostic_active,
                cmd,
                clear_screen,
                binding,
                keyboard_active,
                keyboard_tab,
            )
        )

    def _apply_side_effects(
        self,
        mode,
        first_step,
        is_help_down,
        diagnostic_active,
        cmd,
        clear_screen,
        binding=None,
        keyboard_active=False,
        keyboard_tab=0,
    ):
        if self.tray_app_interface:
            self.tray_app_interface.set_icon(mode, first_step)

        if self.help_interface:
            if is_help_down:
                self.help_interface.show()
            else:
                self.help_interface.hide()
            self._record_overlay("help", is_help_down)

        if self.mouse_interface:
            if mode == MOUSE:
                self.mouse_interface.show()
            else:
                self.mouse_interface.hide()
            self._record_overlay("mouse", mode == MOUSE)

        if self.diagnostics_interface:
            if diagnostic_active:
                self.diagnostics_interface.show()
            else:
                self.diagnostics_interface.hide()
            self._record_overlay("diagnostics", diagnostic_active)

        if self.keyboard_interface:
            if keyboard_active:
                self.keyboard_interface.show(TABS[keyboard_tab % len(TABS)])
            else:
                self.keyboard_interface.hide()
            self._record_overlay("keyboard", keyboard_active)

        if clear_screen and self.mouse_interface:
            self.mouse_interface.clear()
            self._record_overlay("mouse", False)

        # Execute custom command
        if cmd:
            self._run_command(cmd, binding)

    def _record_overlay(self, name, visible):
        if self._visible_overlays[name] != visible:
            self._visible_overlays[name] = visible
            usage.record("overlay", name=name, visible=visible)

    @staticmethod
    def _run_command(cmd: str, binding=None):
        """Launch a config-defined command and forget about it.

        The command is the owner's own config entry, so the shell is the point
        rather than a risk. What was a risk is the pipe os.popen left behind:
        nothing ever read or closed it, so every press leaked a descriptor and
        any command that outproduced the pipe buffer blocked forever. Redirect
        the three streams to DEVNULL and none of that can happen.
        """
        try:
            subprocess.Popen(
                cmd,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # no console window flashing up on Windows; 0 elsewhere
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            usage.record("command_launch", binding=binding, success=True)
        except OSError as error:
            usage.record("command_launch", binding=binding, success=False)
            logger.error(
                "Could not launch configured command: %s (errno=%s)",
                type(error).__name__,
                error.errno,
            )
