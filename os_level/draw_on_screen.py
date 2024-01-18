import ctypes
import logging
import os
import time
import tkinter as tk
from abc import ABC, abstractmethod
from pathlib import Path

import yaml

from os_level.windows_api import get_active_process_name

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10


logger = logging.getLogger(__name__)

class Screenable(ABC):
    @abstractmethod
    def show(self):
        pass
    @abstractmethod
    def hide(self):
        pass



class WinImage():
    def __init__(self):
        self.root = tk.Tk()

    def _draw(self):
        # position of window
        x = 200
        y = 150
        width = 1400
        height = 700
        self.root = tk.Tk()
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)  # window ignored by os manager
        self.root.attributes("-alpha", 0.8)

        self.root.attributes('-topmost', True)

        canvas = tk.Canvas(self.root, width=width, height=height)
        canvas.pack(anchor=tk.CENTER, expand=True)

        process_name = get_active_process_name()
        try:
            text = get_help_app(process_name)
        except:
            text = process_name

        #font = "Arial 10"
        font = "consolas 10"

        canvas.create_text(
            width / 2, height / 2, fill="black", font=font, text=text
        )
        print("try draw", len(text))
        self.root.update()

    def show(self):
        if self.root.children:
            return
        self._draw()

    def clear(self):
        if not self.root.children:
            return
        self.root.destroy()


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

    time.sleep(1)

    app.clear()
    app.clear()
    time.sleep(1)
    app.show()
    time.sleep(1)
    app.clear()
