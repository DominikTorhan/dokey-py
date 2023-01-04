import ctypes
import logging
import os
import time
import tkinter as tk
from pathlib import Path

import yaml

from app.mouse_config import MouseConfig
from os_level.windows_api import get_active_window_rect

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10


logger = logging.getLogger(__name__)


# POINTS = [
#     (0.1, 0.1, "q"),
#     (0.2, 0.1, "w"),
#     (0.3, 0.1, "e"),
#     (0.4, 0.1, "r"),
#     (0.5, 0.1, "t"),
#     (0.6, 0.1, "y"),
#     (0.7, 0.1, "u"),
#     (0.8, 0.1, "i"),
#     (0.9, 0.1, "o"),
#
#     (0.1, 0.5, "a"),
#     (0.2, 0.5, "s"),
#     (0.3, 0.5, "d"),
#     (0.4, 0.5, "f"),
#     (0.5, 0.5, "g"),
#     (0.6, 0.5, "h"),
#     (0.7, 0.5, "j"),
#     (0.8, 0.5, "k"),
#     (0.9, 0.5, "l"),
#
#     (0.1, 0.9, "z"),
#     (0.2, 0.9, "x"),
#     (0.3, 0.9, "c"),
#     (0.4, 0.9, "v"),
#     (0.5, 0.9, "b"),
#     (0.6, 0.9, "n"),
#     (0.7, 0.9, "m"),
#     (0.8, 0.9, ","),
#     (0.9, 0.9, ","),
#
# ]


class MouseLoc:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0


def get_absolute_position_in_active_window(rx: float, ry: float):
    rect = get_active_window_rect()
    x = rect.left
    y = rect.top
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    px = x + width * rx
    py = y + height * ry
    return (px, py)


class MouseImage:
    def __init__(self, mouse_config_path):
        # self.root = None
        self.root = tk.Tk()
        self.is_visible = False
        self.mouse_config = MouseConfig.from_file(mouse_config_path)

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
        #self.root.attributes("-alpha", 0.5)

        self.root.attributes("-topmost", True)



        canvas = tk.Canvas(self.root, bg="blue", width=width, height=height)
        self.root.wm_attributes("-transparentcolor", "blue")
        canvas.pack(anchor=tk.CENTER, expand=True)

        def calc_x(val):
            return (width * val)

        def calc_y(val):
            return (height * val)

        font = "consolas 30"

        for key in self.mouse_config.positions:
            pos = self.mouse_config.positions[key]
            px = calc_x(pos[0] / 100)
            py = calc_y(pos[1] / 100)
            canvas.create_text(px, py, fill="red", font=font, text=key)

        # font = "Arial 10"

        # canvas.create_text(
        #     width / 2, height / 2, fill="black", font=font, text=text
        # )
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
    path = Path(__file__).parent.parent / "app" / "mouse_config.yaml"
    app = MouseImage(path)
    app.show()
    time.sleep(2)
    app.clear()
