import logging
from typing import List, Optional
from pynput import keyboard
from app.app import ListenerABC, OSEvent
from app.events import SendEvent, DoKeyEvent, Event, CMDEvent, WriteEvent
from app.modificators import Modificators
from app.keys import Keys, shift_keys, control_keys, alt_keys, win_keys
from pynput.keyboard import Key, Controller, KeyCode
import time
import ctypes


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

    modifs = Modificators()
    modifs.control = is_modif_active(control_keys)
    modifs.shift = is_modif_active(shift_keys)
    modifs.alt = is_modif_active(alt_keys)
    modifs.win = is_modif_active(win_keys)
    modifs.caps = is_modif_active([Keys.CAPS])  # not sure if that works
    logger.debug(f"os modifs {repr(modifs)}")
    return modifs

def get_foreground_window_title() -> Optional[str]:
    hwnd = user32_dll.GetForegroundWindow()
    length = user32_dll.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32_dll.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value if buf.value else None


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
        if self.is_sending:
            logger.debug(f"Is sending, prevent! Suppress state: {self.listener._suppress}")
            return True
        self.listener._suppress = False
        if is_capslock_on():
            return True
        modifs_os = get_modif_state()
        window_title = get_foreground_window_title()
        is_up = msg == 257 or msg == 261
        key = Keys(data.vkCode)
        os_event = OSEvent()
        os_event.key = key
        os_event.is_key_up = is_up
        os_event.modifs_os = modifs_os
        event = self.func(os_event)
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