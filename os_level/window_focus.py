"""Bring an existing Alt+Tab-style window to the foreground (``__focus__``)."""

import ctypes
import logging
from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM, UINT

from os_level.windows_api import get_process_name


logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi.dll")

GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
DWMWA_CLOAKED = 14
SW_RESTORE = 9

EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

# Declared in full: without argtypes ctypes passes an HWND as a C int, and
# without restype it truncates a returned HWND or LONG_PTR to 32 bits.
user32.EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
user32.EnumWindows.restype = BOOL
user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.GetWindowThreadProcessId.restype = DWORD
user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = BOOL
user32.GetWindowLongPtrW.argtypes = [HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindow.argtypes = [HWND, UINT]
user32.GetWindow.restype = HWND
user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.ShowWindow.restype = BOOL
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = BOOL
dwmapi.DwmGetWindowAttribute.argtypes = [HWND, DWORD, ctypes.c_void_p, DWORD]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def _window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _is_cloaked(hwnd):
    cloaked = DWORD()
    result = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return result == 0 and bool(cloaked.value)


def _is_alt_tab_window(hwnd, title):
    if not title or not user32.IsWindowVisible(hwnd):
        return False
    if _is_cloaked(hwnd):
        return False
    exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if exstyle & WS_EX_TOOLWINDOW and not exstyle & WS_EX_APPWINDOW:
        return False
    return not user32.GetWindow(hwnd, GW_OWNER) or bool(exstyle & WS_EX_APPWINDOW)


def focus_window(process, title_prefix):
    """Focus the first Z-order window matching an executable and title prefix.

    Both comparisons are case-insensitive. Runs on the App worker thread, never
    on the keyboard hook.
    """
    process = process.casefold()
    title_prefix = title_prefix.casefold()
    match = None

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        nonlocal match
        title = _window_text(hwnd)
        # title first: it is cheap, and it keeps get_process_name - which logs
        # a warning for every process it may not open - off unrelated windows
        if not title.casefold().startswith(title_prefix):
            return True
        if not _is_alt_tab_window(hwnd, title):
            return True
        pid = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if get_process_name(pid.value).casefold() == process:
            match = hwnd
            return False
        return True

    user32.EnumWindows(visit, 0)
    if match is None:
        logger.warning("Configured window focus target was not found")
        return False
    if user32.IsIconic(match):
        user32.ShowWindow(match, SW_RESTORE)
    if not user32.SetForegroundWindow(match):
        logger.warning("Windows refused to activate the configured focus target")
        return False
    return True
