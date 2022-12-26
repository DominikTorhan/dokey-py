from collections import defaultdict
from typing import Optional, Dict
import ctypes
import os
from ctypes.wintypes import HWND, DWORD, RECT

user32_dll = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi")


# hwnd = 133116    # refer to the other answers on how to find the hwnd of your window
#
# rect = RECT()
# DMWA_EXTENDED_FRAME_BOUNDS = 9
# dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
#                              ctypes.byref(rect), ctypes.sizeof(rect))
#
# print(rect.left, rect.top, rect.right, rect.bottom)

def get_processes() -> Dict[int, str]:
    output: str = os.popen('wmic process get description, processid').read()
    lines = output.splitlines()
    lines = map(lambda s: s.strip(), lines)
    lines = list(filter(None, lines))
    lines.pop(0) # first line is a header
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
    #title = buf.value if buf.value else None

    lpdw_process_id = ctypes.c_ulong()
    result = user32_dll.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
    process_id = lpdw_process_id.value

    rect = RECT()
    DMWA_EXTENDED_FRAME_BOUNDS = 9
    dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWORD(DMWA_EXTENDED_FRAME_BOUNDS),
                                 ctypes.byref(rect), ctypes.sizeof(rect))

    print(rect.left, rect.top, rect.right, rect.bottom)

    return process_id

def get_active_process_name() -> str:
    pid = get_active_window_process()
    processes = get_processes()
    return processes[pid]

#print(get_active_process_name())
