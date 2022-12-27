import logging
import threading
import tkinter as tk
from PIL import ImageGrab, ImageTk
import ctypes
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10


logger = logging.getLogger(__name__)

class WinImage():
    def __init__(self):
        self.root = tk.Tk()
        self.is_visible = False

    def _draw(self):
        # position of window
        x = 1600
        y = 900
        width = 100
        height = 50

        self.root = tk.Tk()
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.update_idletasks()
        self.root.overrideredirect(True)  # window ignored by os manager
        self.root.attributes("-alpha", 0.2)

        canvas = tk.Canvas(self.root, width=width, height=height)
        canvas.pack(anchor=tk.CENTER, expand=True)

        canvas.create_text(
            width / 2, height / 2, fill="black", font="Arial 10", text="custom string"
        )
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
    app = WinImage()
    app.show()
    app.show()
    app.show()
    app.show()

    time.sleep(2)

    app.clear()
    app.clear()
    time.sleep(1)
    app.show()
    time.sleep(1)
    app.clear()
