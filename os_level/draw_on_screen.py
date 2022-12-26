import tkinter as tk
from PIL import ImageGrab, ImageTk
import ctypes
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # windows 10

# position of window
x = 1600
y = 900
width = 100
height = 50

root = tk.Tk()
root.geometry(f"{width}x{height}+{x}+{y}")
root.resizable(False, False)
root.update_idletasks()
root.overrideredirect(True)  # window ignored by os manager
root.attributes("-alpha", 0.2)

canvas = tk.Canvas(root, width=width, height=height)
canvas.pack(anchor=tk.CENTER, expand=True)

canvas.create_text(
    width / 2, height / 2, fill="black", font="Arial 10", text="custom string"
)

root.mainloop()
# root.destroy()
