import ctypes
import logging
import time
import tkinter as tk
from pathlib import Path

from app.app_state import AppState
from os_level.windows_api import get_active_window_rect

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10


logger = logging.getLogger(__name__)


class DiagnosticWindow:
    def __init__(self, app_state: AppState):
        # self.root = None
        self.root = tk.Tk()
        self.is_visible = False
        self.app_state = app_state

    def _draw(self):
        # position of window
        rect = get_active_window_rect()

        x = rect.left
        y = rect.top

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        self.root = tk.Tk()
        # self.root = tk.Toplevel()
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        # self.root.update_idletasks()
        self.root.overrideredirect(True)  # window ignored by os manager
        # self.root.attributes("-alpha", 0.5)

        self.root.attributes("-topmost", True)

        canvas = tk.Canvas(self.root, bg="blue", width=width, height=height)
        self.root.wm_attributes("-transparentcolor", "blue")
        canvas.pack(anchor=tk.CENTER, expand=True)

        font = "consolas 20"

        # font = "Arial 10"
        lines = [
            "diagnostic info",
            f"mode: {self.app_state.mode}",
            f"first step: {self.app_state.first_step}",
            "",
        ]

        text = "\n".join(lines)

        canvas.create_text(150, height / 2, fill="black", font=font, text=text)
        self.root.update()

    def show(self):
        if self.is_visible:
            return
        self._draw()
        self.is_visible = True

    def clear(self):
        if not self.is_visible:
            return
        self.root.destroy()
        self.is_visible = False


if __name__ == "__main__":
    app_state = AppState()
    app = DiagnosticWindow(app_state)
    app.show()
    time.sleep(2)
    app.clear()
