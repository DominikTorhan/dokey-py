"""Focus existing Alt+Tab windows, optionally launching when none match."""

import ctypes
import logging
import subprocess
import uuid
from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM, UINT

from os_level.windows_api import get_process_name


logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("User32.dll")
dwmapi = ctypes.WinDLL("dwmapi.dll")
shell32 = ctypes.WinDLL("shell32.dll")
ole32 = ctypes.WinDLL("ole32.dll")

GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
DWMWA_CLOAKED = 14
SW_RESTORE = 9
VT_LPWSTR = 31


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value):
        parsed = uuid.UUID(value)
        return cls(
            parsed.time_low,
            parsed.time_mid,
            parsed.time_hi_version,
            (ctypes.c_ubyte * 8)(*parsed.bytes[8:]),
        )


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", DWORD)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("value", ctypes.c_void_p),
        ("value2", ctypes.c_void_p),
    ]


IID_IPROPERTY_STORE = GUID.from_string("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
PKEY_APP_USER_MODEL_ID = PROPERTYKEY(
    GUID.from_string("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3"), 5
)

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
shell32.SHGetPropertyStoreForWindow.argtypes = [
    HWND,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long
ole32.CoInitialize.argtypes = [ctypes.c_void_p]
ole32.CoInitialize.restype = ctypes.c_long
ole32.CoUninitialize.argtypes = []
ole32.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
ole32.PropVariantClear.restype = ctypes.c_long


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


def _window_app_id(hwnd):
    """Return the window's explicit AppUserModelID, or an empty string."""
    initialized = ole32.CoInitialize(None) >= 0
    store = ctypes.c_void_p()
    try:
        result = shell32.SHGetPropertyStoreForWindow(
            hwnd, ctypes.byref(IID_IPROPERTY_STORE), ctypes.byref(store)
        )
        if result < 0 or not store.value:
            return ""

        vtable = ctypes.cast(
            store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_value = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(PROPERTYKEY),
            ctypes.POINTER(PROPVARIANT),
        )(vtable[5])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        value = PROPVARIANT()
        try:
            result = get_value(
                store, ctypes.byref(PKEY_APP_USER_MODEL_ID), ctypes.byref(value)
            )
            if result < 0:
                return ""
            if value.vt != VT_LPWSTR or not value.value:
                return ""
            return ctypes.wstring_at(value.value)
        finally:
            ole32.PropVariantClear(ctypes.byref(value))
            release(store)
    finally:
        if initialized:
            ole32.CoUninitialize()


def _activate_window(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))


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
    if not _activate_window(match):
        logger.warning("Windows refused to activate the configured focus target")
        return False
    return True


def focus_or_launch(process, app_id, cmd):
    """Focus the newest matching AppUserModelID, or launch its command."""
    process = process.casefold()
    app_id = app_id.casefold()
    match = None

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        nonlocal match
        title = _window_text(hwnd)
        if not _is_alt_tab_window(hwnd, title):
            return True
        pid = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if get_process_name(pid.value).casefold() != process:
            return True
        if _window_app_id(hwnd).casefold() == app_id:
            match = hwnd
            return False
        return True

    user32.EnumWindows(visit, 0)
    if match is not None:
        if not _activate_window(match):
            logger.warning("Windows refused to activate the configured focus target")
            return False
        return "focused"

    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as error:
        logger.error(
            "Could not launch configured focus target: %s (errno=%s)",
            type(error).__name__,
            error.errno,
        )
        return False
    return "launched"
