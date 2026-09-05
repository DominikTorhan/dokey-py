"""Foreground-window queries on raw ctypes - replaces psutil."""

import ctypes
import logging
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND, LPWSTR, RECT

user32_dll = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi")
kernel32_dll = ctypes.WinDLL("kernel32.dll")

logger = logging.getLogger(__name__)

# PROCESS_QUERY_LIMITED_INFORMATION succeeds against elevated processes, where
# the older PROCESS_QUERY_INFORMATION is denied.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH_LONG = 32768

DWMWA_EXTENDED_FRAME_BOUNDS = 9

# Declaring these matters on 64-bit: without an explicit restype ctypes assumes
# int and truncates the returned HANDLE.
kernel32_dll.OpenProcess.restype = HANDLE
kernel32_dll.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
kernel32_dll.QueryFullProcessImageNameW.restype = BOOL
kernel32_dll.QueryFullProcessImageNameW.argtypes = [
    HANDLE,
    DWORD,
    LPWSTR,
    ctypes.POINTER(DWORD),
]
kernel32_dll.CloseHandle.restype = BOOL
kernel32_dll.CloseHandle.argtypes = [HANDLE]


def get_active_window_process() -> int:
    hwnd = user32_dll.GetForegroundWindow()
    process_id = ctypes.c_ulong()
    user32_dll.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    return process_id.value


def get_active_window_rect() -> RECT:
    hwnd = user32_dll.GetForegroundWindow()
    rect = RECT()
    dwmapi.DwmGetWindowAttribute(
        HWND(hwnd),
        DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    return rect


def get_process_name(pid: int) -> str:
    """Executable name for a pid, e.g. "chrome.exe".

    Returns "" instead of raising when the process is gone or the query is
    denied - this runs on the help-overlay draw path, which should degrade
    rather than blow up.
    """
    handle = kernel32_dll.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        logger.warning(f"OpenProcess failed for pid {pid}")
        return ""
    try:
        size = DWORD(MAX_PATH_LONG)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32_dll.QueryFullProcessImageNameW(
            handle, 0, buf, ctypes.byref(size)
        ):
            logger.warning(f"QueryFullProcessImageNameW failed for pid {pid}")
            return ""
        # full path -> basename, matching what psutil's Process.name() returned
        return buf.value.rsplit("\\", 1)[-1]
    finally:
        kernel32_dll.CloseHandle(handle)


def get_active_process_name() -> str:
    return get_process_name(get_active_window_process())


if __name__ == "__main__":
    print(get_active_process_name())
