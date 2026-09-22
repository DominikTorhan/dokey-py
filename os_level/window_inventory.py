"""Best-effort inventory of Alt+Tab-style windows and application tabs."""

import ctypes
import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM, RECT

from os_level.windows_api import get_process_name


logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi.dll")

GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
SW_RESTORE = 9

EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
user32.EnumWindows.restype = BOOL
user32.GetWindowTextLengthW.argtypes = [HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
user32.GetWindowThreadProcessId.restype = DWORD
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND
user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.ShowWindow.restype = BOOL
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = BOOL


def _window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value.strip()


def _class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _dwm_value(hwnd, attribute, value):
    return (
        dwmapi.DwmGetWindowAttribute(
            hwnd,
            attribute,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        == 0
    )


def _is_alt_tab_window(hwnd, title):
    if not title or not user32.IsWindowVisible(hwnd):
        return False
    cloaked = DWORD()
    if _dwm_value(hwnd, DWMWA_CLOAKED, cloaked) and cloaked.value:
        return False
    exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if exstyle & WS_EX_TOOLWINDOW and not exstyle & WS_EX_APPWINDOW:
        return False
    return not user32.GetWindow(hwnd, GW_OWNER) or bool(exstyle & WS_EX_APPWINDOW)


def _window_bounds(hwnd):
    rect = RECT()
    if not _dwm_value(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, rect):
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return [rect.left, rect.top, rect.right, rect.bottom]


def list_windows():
    """Return visible task windows in Windows' current Z order."""
    foreground = user32.GetForegroundWindow()
    windows = []

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        title = _window_text(hwnd)
        if not _is_alt_tab_window(hwnd, title):
            return True
        pid = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append(
            {
                "hwnd": int(hwnd),
                "pid": pid.value,
                "process": get_process_name(pid.value) or "unknown",
                "class": _class_name(hwnd),
                "title": title,
                "bounds": _window_bounds(hwnd),
                "state": (
                    "minimized"
                    if user32.IsIconic(hwnd)
                    else "maximized" if user32.IsZoomed(hwnd) else "normal"
                ),
                "foreground": hwnd == foreground,
            }
        )
        return True

    if not user32.EnumWindows(visit, 0):
        logger.warning("EnumWindows failed")
    return windows


def focus_window(process, title_prefix):
    """Focus the first Z-order window matching an executable and title prefix."""
    process = process.casefold()
    title_prefix = title_prefix.casefold()
    match = None

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        nonlocal match
        title = _window_text(hwnd)
        if not _is_alt_tab_window(hwnd, title):
            return True
        pid = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if (
            get_process_name(pid.value).casefold() == process
            and title.casefold().startswith(title_prefix)
        ):
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


def _chromium_ports():
    configured = os.environ.get("DOKEY_CDP_PORTS", "9222,9223")
    ports = []
    for item in configured.split(","):
        try:
            ports.append(int(item.strip()))
        except ValueError:
            logger.warning("Ignoring invalid DOKEY_CDP_PORTS item: %r", item)
    return ports


def list_browser_tabs():
    """Read Chromium tabs exposed by an opt-in local DevTools endpoint."""
    tabs = []
    for port in _chromium_ports():
        url = f"http://127.0.0.1:{port}/json/list"
        try:
            with urllib.request.urlopen(url, timeout=0.25) as response:
                targets = json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            continue
        for target in targets:
            if target.get("type") not in {"page", "webview"}:
                continue
            tabs.append(
                {
                    "port": port,
                    "title": target.get("title", ""),
                    "url": target.get("url", ""),
                    "type": target.get("type", ""),
                    "id": target.get("id", ""),
                }
            )
    return tabs


def list_wezterm_tabs():
    """Return WezTerm panes; tab_id and window_id preserve their grouping."""
    try:
        result = subprocess.run(
            ["wezterm", "cli", "list", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        panes = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return panes if isinstance(panes, list) else []


def snapshot():
    return {
        "windows": list_windows(),
        "browser_tabs": list_browser_tabs(),
        "wezterm_panes": list_wezterm_tabs(),
    }
