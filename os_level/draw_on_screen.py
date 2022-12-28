import os
import logging
import threading
import tkinter as tk

import yaml
from PIL import ImageGrab, ImageTk
import ctypes
import time
from pathlib import Path
from os_level.windows_api import get_active_process_name


ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10


logger = logging.getLogger(__name__)

class WinImage():
    def __init__(self):
        self.root = tk.Tk()
        self.is_visible = False

    def _draw(self):
        # position of window
        x = 200
        y = 150
        width = 1400
        height = 700

        self.root = tk.Tk()
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        #self.root.update_idletasks()
        self.root.overrideredirect(True)  # window ignored by os manager
        self.root.attributes("-alpha", 0.4)

        canvas = tk.Canvas(self.root, width=width, height=height)
        canvas.pack(anchor=tk.CENTER, expand=True)

        process_name = get_active_process_name()
        try:
            text = get_help_app(process_name)
        except:
            text = process_name

        canvas.create_text(
            width / 2, height / 2, fill="black", font="Arial 10", text=text
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


def get_help_app(process_name):
    path = Path(os.environ["HOMEPATH"]) / ".dokey" / "help.yaml"
    content = process_name
    with open(path, "r") as f:
        data: dict = yaml.safe_load(f)
    for key in data:
        if key not in process_name.lower():
            continue
        content += "\n" + "\n".join(data[key])
    return content

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
