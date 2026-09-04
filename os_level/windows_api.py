from collections import defaultdict
from typing import Optional, Dict
import ctypes
import logging
import os
from ctypes.wintypes import BOOL, DWORD, HANDLE, HWND, LPWSTR, RECT

user32_dll = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi")
kernel32_dll = ctypes.WinDLL("kernel32.dll")

logger = logging.getLogger(__name__)

# PROCESS_QUERY_LIMITED_INFORMATION succeeds against elevated processes, where
# the older PROCESS_QUERY_INFORMATION is denied.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH_LONG = 32768

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


# hwnd = 133116    # refer to the other answers on how to find the hwnd of your window
#
# rect = RECT()
# DMWA_EXTENDED_FRAME_BOUNDS = 9
# dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
#                              ctypes.byref(rect), ctypes.sizeof(rect))
#
# print(rect.left, rect.top, rect.right, rect.bottom)


def get_processes() -> Dict[int, str]:
    # solution 2
    pids = []
    a = os.popen("tasklist").readlines()
    for x in a:
        try:
            pids.append(int(x[29:34]))
        except:
            pass
    for each in pids:
        print(each)

    # solution 1
    output: str = os.popen("wmic process get description, processid").read()
    lines = output.splitlines()
    lines = map(lambda s: s.strip(), lines)
    lines = list(filter(None, lines))
    lines.pop(0)  # first line is a header
    processes = {}
    for line in lines:
        strs = line.split()
        pid = int(strs[-1])
        name = " ".join(strs[:-1])
        processes[pid] = name
    return processes


def get_active_window_process() -> int:
    hwnd = user32_dll.GetForegroundWindow()
    length = user32_dll.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32_dll.GetWindowTextW(hwnd, buf, length + 1)
    # title = buf.value if buf.value else None

    lpdw_process_id = ctypes.c_ulong()
    result = user32_dll.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
    process_id = lpdw_process_id.value

    rect = get_active_window_rect()

    # rect = RECT()
    # DMWA_EXTENDED_FRAME_BOUNDS = 9
    # dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
    #                              ctypes.byref(rect), ctypes.sizeof(rect))

    print(rect.left, rect.top, rect.right, rect.bottom)

    return process_id


def get_active_window_rect():
    hwnd = user32_dll.GetForegroundWindow()
    rect = RECT()
    DMWA_EXTENDED_FRAME_BOUNDS = 9
    dwmapi.DwmGetWindowAttribute(
        HWND(hwnd),
        DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
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
    pid = get_active_window_process()
    name = get_process_name(pid)
    print(name)
    return name


# print(get_active_process_name())
if __name__ == "__main__":
    get_active_process_name()
