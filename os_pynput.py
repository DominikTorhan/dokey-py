from typing import List
from pynput import keyboard
from app.app import ListenerABC
from app.enums import Keys, keyboard_to_dokey_map
from pynput.keyboard import Key, Controller, KeyCode
import time
import ctypes

user32_dll = ctypes.WinDLL("User32.dll")

def is_capslock_on():
    return True if user32_dll.GetKeyState(0x14) else False


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

    def win32_event_filter(self, msg, data):  # happens before "on_press", "on_release"
        """
        msg: 256 keydown, 257, keyup, 260 syskeydown, 261 up
        """
        #print("SYS", msg, data)
        if self.is_sending:
            print(f"Is sending, prevent! Suppress state: {self.listener._suppress}")
            return True
        self.listener._suppress = False
        if is_capslock_on():
            return True
        is_up = msg == 257 or msg == 261
        is_up_str = "up" if is_up else "down"
        key = Keys(data.vkCode)
        print(key, is_up_str, msg, "vkcode: ", data.vkCode, data)
        send, prev = self.func(key, is_up)
        if send:
            if Keys.COMMAND_EXIT in send:
                self.listener.stop()
                self.listener._suppress = True
                return False
            self.is_sending = True
            self.send_keys(send)
            self.is_sending = False
            self.listener._suppress = True
            return False
        if prev:
            self.listener._suppress = True
            return False
        return True

    def send_keys(self, send: List[Keys]):
        keyboard = Controller()
        modifs = []
        print("__WILL_SEND__: ", send)

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
        print("__SENT__")
