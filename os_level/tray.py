"""Windows tray icon via Shell_NotifyIcon - replaces pystray (and Pillow).

The icon runs on its own thread with its own message pump: a window must be
created on the thread that pumps its messages. LoadImageW reads the .ico files
in assets/ directly, which is why Pillow is no longer needed.
"""

import ctypes
import logging
import threading
from ctypes import wintypes

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


# Explicit signatures: on 64-bit, an undeclared restype defaults to int and
# truncates every returned handle.
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class TrayIcon:
    """Minimal replacement for the slice of pystray.Icon that DoKey used."""

    def __init__(self, name: str, icon_path: str, tooltip: str = None):
        self.name = name
        self.tooltip = tooltip or name
        self._icon_path = icon_path
        self._hwnd = None
        self._icon_cache = {}
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread = None
        # keep a reference: if the WNDPROC is garbage collected Windows calls
        # into freed memory
        self._wndproc = WNDPROC(self._on_message)
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

    def run_detached(self, timeout: float = 5.0):
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            logger.warning("Tray icon did not come up within %ss", timeout)

    def set_icon(self, icon_path: str):
        # called from the keyboard hook on every key event, and that callback
        # must stay fast (Windows unhooks a slow one), so do nothing unless the
        # icon really changed
        if icon_path == self._icon_path:
            return
        self._icon_path = icon_path
        with self._lock:
            if not self._hwnd:
                return
            self._notify(NIM_MODIFY)

    def stop(self):
        with self._lock:
            if not self._hwnd:
                return
            self._notify(NIM_DELETE)
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)

    def _load_icon(self, path: str):
        if path not in self._icon_cache:
            handle = user32.LoadImageW(
                None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
            if not handle:
                logger.error(
                    "LoadImageW failed for %s (err %s)", path, ctypes.get_last_error()
                )
            self._icon_cache[path] = handle
        return self._icon_cache[path]

    def _notify(self, message: int) -> bool:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_TIP
        nid.hIcon = self._load_icon(self._icon_path)
        nid.szTip = self.tooltip[:127]
        ok = shell32.Shell_NotifyIconW(message, ctypes.byref(nid))
        if not ok and message != NIM_DELETE:
            logger.error(
                "Shell_NotifyIcon(%s) failed (err %s)",
                message,
                ctypes.get_last_error(),
            )
        return bool(ok)

    def _on_message(self, hwnd, msg, wparam, lparam):
        # explorer.exe restarted - the icon is gone and has to be re-added
        if msg == self._taskbar_created:
            with self._lock:
                self._notify(NIM_ADD)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        try:
            hinstance = kernel32.GetModuleHandleW(None)
            class_name = f"DoKeyTray_{id(self)}"

            wnd_class = WNDCLASSW()
            wnd_class.lpfnWndProc = self._wndproc
            wnd_class.hInstance = hinstance
            wnd_class.lpszClassName = class_name
            if not user32.RegisterClassW(ctypes.byref(wnd_class)):
                logger.error("RegisterClassW failed (err %s)", ctypes.get_last_error())
                return

            hwnd = user32.CreateWindowExW(
                0, class_name, self.name, 0, 0, 0, 0, 0, None, None, hinstance, None
            )
            if not hwnd:
                logger.error("CreateWindowExW failed (err %s)", ctypes.get_last_error())
                return

            with self._lock:
                self._hwnd = hwnd
                self._notify(NIM_ADD)
        finally:
            self._ready.set()

        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):  # WM_QUIT, or an error
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        with self._lock:
            self._hwnd = None
        logger.info("Tray message loop finished.")
