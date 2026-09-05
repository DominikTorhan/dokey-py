"""Windows keyboard hook and input injection on raw ctypes - replaces pynput.

Two things get simpler by owning the hook:

* Returning 1 from a WH_KEYBOARD_LL callback is the documented way to swallow a
  key, so nothing has to poke at pynput's private ``_suppress`` attribute.
* Keystrokes we inject carry DOKEY_EXTRA_INFO in ``dwExtraInfo`` and are ignored
  on the way back in. That replaces the old ``is_sending`` flag, which could not
  distinguish our own echo from a real key pressed at the same moment.

The callback must stay fast: Windows silently unhooks a low-level hook whose
callback overruns LowLevelHooksTimeout (300 ms by default), leaving DoKey
running but no longer remapping anything. Deciding what to send is quick;
everything slow - overlays, custom commands - is deferred by App onto its own
thread.
"""

import ctypes
import logging
from ctypes import wintypes
from typing import List

from app.app import ListenerABC, OSEvent
from app.events import (
    SendEvent,
    DoKeyEvent,
    Event,
    CMDEvent,
    WriteEvent,
    EventLike,
    MouseEvent,
)
from app.keys import Keys, shift_keys, control_keys, alt_keys, win_keys
from app.modifs import Modifs
from os_level.mouse_window import get_absolute_position_in_active_window

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
KEY_UP_MESSAGES = (WM_KEYUP, WM_SYSKEYUP)

VK_CAPITAL = 0x14

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004

# tags our own injected input so the hook can recognise and skip it
DOKEY_EXTRA_INFO = 0x22D0E4

# keys that need the extended-key flag or they arrive as their numpad twins
EXTENDED_VKS = frozenset(
    {
        Keys.PAGE_UP.value,
        Keys.PAGE_DOWN.value,
        Keys.END.value,
        Keys.HOME.value,
        Keys.LEFT.value,
        Keys.UP.value,
        Keys.RIGHT.value,
        Keys.DOWN.value,
        Keys.INSERT.value,
        Keys.DELETE.value,
        Keys.PRINT_SCREEN.value,
        Keys.RIGHT_CTRL.value,
        Keys.RIGHT_ALT.value,
        Keys.LEFT_WIN.value,
        Keys.RIGHT_WIN.value,
        Keys.MENU.value,
    }
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# Explicit signatures: on 64-bit an undeclared restype defaults to int and
# truncates every returned handle.
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


def is_capslock_on() -> bool:
    # kept as-is from the pynput implementation: caps lock toggled on is the
    # "pass everything through" escape hatch
    return True if user32.GetKeyState(VK_CAPITAL) else False


def get_modif_state() -> Modifs:
    def is_modif_active(keys: List[Keys]):
        return any(user32.GetAsyncKeyState(key.value) for key in keys)

    modifs = Modifs()
    modifs.control = is_modif_active(control_keys)
    modifs.shift = is_modif_active(shift_keys)
    modifs.alt = is_modif_active(alt_keys)
    modifs.win = is_modif_active(win_keys)
    logger.debug(f"os modifs {repr(modifs)}")
    return modifs


def _key_input(vk: int, is_up: bool) -> INPUT:
    flags = KEYEVENTF_KEYUP if is_up else 0
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    item = INPUT(type=INPUT_KEYBOARD)
    item.ki = KEYBDINPUT(
        wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=DOKEY_EXTRA_INFO
    )
    return item


def _char_input(char: str, is_up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if is_up else 0)
    item = INPUT(type=INPUT_KEYBOARD)
    item.ki = KEYBDINPUT(
        wVk=0, wScan=ord(char), dwFlags=flags, time=0, dwExtraInfo=DOKEY_EXTRA_INFO
    )
    return item


def _mouse_input(flags: int) -> INPUT:
    item = INPUT(type=INPUT_MOUSE)
    item.mi = MOUSEINPUT(
        dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=DOKEY_EXTRA_INFO
    )
    return item


def _send(items: List[INPUT]) -> None:
    if not items:
        return
    array = (INPUT * len(items))(*items)
    sent = user32.SendInput(len(items), array, ctypes.sizeof(INPUT))
    if sent != len(items):
        logger.error(
            "SendInput sent %s of %s (err %s)",
            sent,
            len(items),
            ctypes.get_last_error(),
        )


class WindowsListener(ListenerABC):
    """Low-level keyboard hook. run() blocks on the hook's message pump."""

    def __init__(self):
        self.func = None
        self._hook = None
        # keep a reference: if the HOOKPROC is collected Windows calls freed memory
        self._proc = HOOKPROC(self._on_key)

    def run(self, func):
        self.func = func
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, module, 0)
        if not self._hook:
            raise OSError(
                f"SetWindowsHookExW failed (err {ctypes.get_last_error()})"
            )
        logger.info("Keyboard hook installed.")
        try:
            msg = wintypes.MSG()
            while True:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result in (0, -1):  # WM_QUIT, or an error
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            logger.info("Keyboard hook removed.")

    def _on_key(self, code, wparam, lparam):
        if code != HC_ACTION:
            return user32.CallNextHookEx(None, code, wparam, lparam)

        data = KBDLLHOOKSTRUCT.from_address(lparam)

        # our own injected keystrokes must not be re-processed
        if data.dwExtraInfo == DOKEY_EXTRA_INFO:
            return user32.CallNextHookEx(None, code, wparam, lparam)
        if is_capslock_on():
            return user32.CallNextHookEx(None, code, wparam, lparam)

        try:
            key = Keys(data.vkCode)
        except ValueError:
            logger.critical(f"Missing VK {data.vkCode} in Keys!")
            return user32.CallNextHookEx(None, code, wparam, lparam)

        os_event = OSEvent()
        os_event.key = key
        os_event.is_key_up = wparam in KEY_UP_MESSAGES
        os_event.modifs_os = get_modif_state()

        try:
            event: EventLike = self.func(os_event)
        except Exception:
            # never let an exception escape into the hook
            logger.exception("Error handling key event")
            return user32.CallNextHookEx(None, code, wparam, lparam)

        if self._perform(event):
            return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _perform(self, event: EventLike) -> bool:
        """Do the fast part and report whether the original key is swallowed."""
        if isinstance(event, DoKeyEvent):
            if event.event_type == "exit":
                user32.PostQuitMessage(0)
            return True
        if isinstance(event, SendEvent):
            self.send_keys(event.send)
            return True
        if isinstance(event, WriteEvent):
            self.write_text(event.text)
            return True
        if isinstance(event, MouseEvent):
            self.exec_mouse(event.rx, event.ry)
            return True
        if isinstance(event, CMDEvent):
            return True  # App runs the command off the hook thread
        if isinstance(event, Event):
            return event.prevent_key_process
        return False

    def send_keys(self, send: List[Keys]):
        modifs: List[Keys] = []
        for key in send:
            if key.is_modif():
                modifs.append(key)
                continue
            items = [_key_input(m.value, False) for m in modifs]
            items.append(_key_input(key.value, False))
            items.append(_key_input(key.value, True))
            items.extend(_key_input(m.value, True) for m in reversed(modifs))
            _send(items)
            modifs = []

    def write_text(self, text: str):
        logger.info(f"WRITE_EVENT: {text}")
        items = []
        for char in text:
            items.append(_char_input(char, False))
            items.append(_char_input(char, True))
        _send(items)

    def exec_mouse(self, rx: float, ry: float):
        x, y = get_absolute_position_in_active_window(rx, ry)
        user32.SetCursorPos(int(x), int(y))
        _send([_mouse_input(MOUSEEVENTF_LEFTDOWN), _mouse_input(MOUSEEVENTF_LEFTUP)])
