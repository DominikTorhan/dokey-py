"""Solid text overlay for the experimental open-window inventory."""

import logging
import tkinter as tk
import tkinter.font as tkfont

from app.window_inventory_format import format_inventory


logger = logging.getLogger(__name__)

BACKGROUND = "#171a1f"
FOREGROUND = "#e6e8eb"
DIM = "#89909a"
ACCENT = "#61c0bf"


class WindowListWindow:
    def __init__(self, inventory):
        self.inventory = inventory
        self.root = None
        self.text = None
        self.is_visible = False
        self.revision = None
        self.scroll = 1

    def show(self, revision=0, scroll=1):
        try:
            if (
                self.is_visible
                and revision == self.revision
                and scroll == self.scroll
            ):
                return
            content = (
                format_inventory(self.inventory())
                if revision != self.revision
                else None
            )
            if self.is_visible:
                if content is not None:
                    self.text.configure(state="normal")
                    self.text.delete("1.0", "end")
                    self.text.insert("1.0", content)
                    self.text.configure(state="disabled")
                self.text.see(f"{scroll}.0")
                self.root.update()
                self.revision = revision
                self.scroll = scroll
                return

            root = tk.Tk()
            root.configure(bg=BACKGROUND)
            root.title("DoKey open windows POC")
            width = min(1280, root.winfo_screenwidth() - 80)
            height = min(820, root.winfo_screenheight() - 120)
            family = (
                "Consolas" if "Consolas" in tkfont.families(root) else "TkFixedFont"
            )
            frame = tk.Frame(root, bg=BACKGROUND)
            frame.pack(fill="both", expand=True, padx=20, pady=16)
            header = tk.Label(
                frame,
                text=(
                    "WINDOW INVENTORY     Caps + ] refresh     "
                    "Up/Down/Page/Home/End scroll     ESC close"
                ),
                bg=BACKGROUND,
                fg=ACCENT,
                anchor="w",
                font=(family, 12, "bold"),
            )
            header.pack(fill="x", pady=(0, 10))
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side="right", fill="y")
            text = tk.Text(
                frame,
                bg=BACKGROUND,
                fg=FOREGROUND,
                insertbackground=FOREGROUND,
                selectbackground=DIM,
                relief="flat",
                wrap="none",
                font=(family, 10),
                yscrollcommand=scrollbar.set,
                padx=8,
                pady=8,
            )
            text.insert("1.0", content)
            text.configure(state="disabled")
            text.pack(side="left", fill="both", expand=True)
            scrollbar.configure(command=text.yview)
            self.root = root
            self.text = text
            screen_x = (root.winfo_screenwidth() - width) // 2
            screen_y = (root.winfo_screenheight() - height) // 3
            root.geometry(f"{width}x{height}+{max(0, screen_x)}+{max(0, screen_y)}")
            root.attributes("-topmost", True)
            root.overrideredirect(True)
            root.update()
            self.is_visible = True
            self.revision = revision
            self.scroll = scroll
        except tk.TclError:
            logger.exception("Could not open the window inventory")
            self.root = self.text = None
            self.is_visible = False
            self.revision = None
            self.scroll = 1

    def clear(self):
        if not self.is_visible:
            return
        try:
            self.root.destroy()
        except tk.TclError:
            logger.exception("Could not close the window inventory")
        finally:
            self.root = self.text = None
            self.is_visible = False
            self.revision = None
            self.scroll = 1
