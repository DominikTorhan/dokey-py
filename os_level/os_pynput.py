import logging
from typing import List, Optional
import ctypes

from pynput import keyboard
from pynput.keyboard import Key, Controller, KeyCode

from app.app import ListenerABC, OSEvent
from app.events import SendEvent, DoKeyEvent, Event, CMDEvent, WriteEvent, EventLike
from app.modifs import Modifs
from app.keys import Keys, shift_keys, control_keys, alt_keys, win_keys

from os_level.windows_api import get_active_process_name

logger = logging.getLogger(__name__)


user32_dll = ctypes.WinDLL("User32.dll")


def is_capslock_on():
    return True if user32_dll.GetKeyState(0x14) else False


# user32 = WinDLL('user32')
# gaks = user32.GetAsyncKeyState
# gks = user32.GetKeyState
#
# VK_SHIFT         = 0x10
# VK_CONTROL       = 0x11
# VK_MENU = VK_ALT = 0x12
# VK_CAPITAL       = 0x14
# VK_SCROLL        = 0x91
#
# shift_down = (gaks(VK_SHIFT) & 0x8000) != 0
# control_down = (gaks(VK_CONTROL) & 0x8000) != 0
# alt_down = (gaks(VK_ALT) & 0x8000) != 0
# capslock_down = (gks(VK_CAPITAL) & 0x0001) != 0
# scrolllock_down = (gks(VK_SCROLL) & 0x0001) != 0


def get_modif_state():
    def is_modif_active(keys: List[Keys]):
        return any(user32_dll.GetAsyncKeyState(key.value) for key in keys)

    modifs = Modifs()
    modifs.control = is_modif_active(control_keys)
    modifs.shift = is_modif_active(shift_keys)
    modifs.alt = is_modif_active(alt_keys)
    modifs.win = is_modif_active(win_keys)
    logger.debug(f"os modifs {repr(modifs)}")
    return modifs

class PynpytListener(ListenerABC):
    def __init__(self):
        self.listener = keyboard.Listener(
            win32_event_filter=self.win32_event_filter,
            suppress=False,
        )
        self.func = None
        self.is_sending = False

    def run(self, func):
        self.func = func
        with self.listener as ml:
            ml.join()

    def win32_event_filter(
        self, msg, data
    ) -> bool:  # happens before "on_press", "on_release"
        """
        msg: 256 keydown, 257, keyup, 260 syskeydown, 261 up
        """
        #logger.info(f"msg={msg} flags={data.flags} vkCode={data.vkCode} scanCode={data.scanCode} time={data.time}")
        if self.is_sending:
            logger.debug(f"Is sending, prevent! Suppress state: {self.listener._suppress}")
            return True
        self.listener._suppress = False
        if is_capslock_on():
            return True
        modifs_os = get_modif_state()
        is_up = msg == 257 or msg == 261
        try:
            key = Keys(data.vkCode)
        except:
            logger.critical(f"Missing VK {data.vkCode} in Keys!")
            return True
        os_event = OSEvent()
        os_event.key = key
        os_event.is_key_up = is_up
        os_event.modifs_os = modifs_os
        event: EventLike = self.func(os_event)
        if isinstance(event, DoKeyEvent):
            self.listener.stop()
            self.listener._suppress = True
            return False
        if isinstance(event, SendEvent):
            self.is_sending = True
            self.send_keys(event.send)
            self.is_sending = False
            self.listener._suppress = True
            return False
        if isinstance(event, CMDEvent):
            self.listener._suppress = True
            return False
        if isinstance(event, WriteEvent):
            self.is_sending = True
            self.write_text(event.text)
            self.is_sending = False
            self.listener._suppress = True
            return False
        if isinstance(event, Event):
            if event.prevent_key_process:
                self.listener._suppress = True
                return False
        return True

    def send_keys(self, send: List[Keys]):
        keyboard = Controller()
        modifs = []
        logger.debug("__WILL_SEND__: ", send)

        for key in send:
            key_code = KeyCode.from_vk(key.value)
            if key.is_modif():
                modifs.append(key_code)
                continue
            # key_str = key.to_string()
            with keyboard.pressed(*modifs):
                keyboard.press(key_code)
                keyboard.release(key_code)
            modifs = []
        logger.debug("__SENT__")

    def write_text(self, text: str):
        logger.info(f"WRITE_EVENT: {text}")
        keyboard = Controller()
        for char in text:
            keyboard.press(char)
            keyboard.release(char)

    def exec_mouse(self):
        from pynput.mouse import Controller
        mouse = Controller()
        mouse.position = (10, 10)

        #mouse.
        pass