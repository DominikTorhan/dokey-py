"""Full-keyboard cheat sheet: what every key does, one tab per way of pressing it.

Unlike the other overlays this one is a solid, centred panel rather than a
transparent click-through. It stays up until dismissed, and something you read
wants a legible background; something you glance at does not.

It is also the one module under os_level/ that imports on Linux. Everything
Windows-specific is guarded, so tools/keyboard_preview.py can draw the real
config under WSLg - the only way to iterate on the picture without a Windows
session. It imports no other os_level module; keep it that way.
"""

import logging
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, List

from app.keyboard_layout import ROW_WIDTH, ROWS, TABS, KeyCap

logger = logging.getLogger(__name__)

try:  # Windows: per-monitor DPI, or the caps render blurry on a scaled display
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):  # any non-Windows box, WSL included
    pass

UNIT = 76  # pixels per key unit; a letter key is one unit wide
ROW_HEIGHT = 78
GAP = 5
PAD = 22
HEADER = 46
FOOTER = 40

BACKGROUND = "#1b1b1f"
CAP_FILL = "#2b2b31"
CAP_STRUCTURAL = "#212125"
CAP_SPECIAL = "#3a3020"
CAP_EDGE = "#45454d"
LABEL = "#e8e8ea"
LABEL_DIM = "#67676f"
DETAIL = "#8a8a94"
HINT = "#9a9aa4"

TAB_ACTIVE_FILL = "#33333c"
TAB_ACTIVE_EDGE = "#5c5c6a"

# One colour per kind of binding, so the eye can sort them without reading:
# a remap, a DoKey control, or a first step that opens a two-step chord.
TEXT_BY_ROLE = {
    "": "#5bc8b0",
    "structural": "#5bc8b0",
    "control": "#e08a5b",
    "prefix": "#9b8ce0",
    "special_key": "#dcc98a",
}


class KeyboardWindow:
    """Draws the rows from app.keyboard_layout.build(), one tab at a time.

    Takes a callable rather than the rows themselves so that every open reads
    the current Config - the overlay should never describe a keymap that has
    since been edited.
    """

    def __init__(
        self,
        build_rows: Callable[[str], List[List[KeyCap]]],
        footer_notes: Callable[[], list] = None,
        overlay=True,
    ):
        self.build_rows = build_rows
        self.footer_notes = footer_notes or (lambda: [])
        self.overlay = overlay
        self.root = None
        self.canvas = None
        self.fonts = None
        self.tab = TABS[0]
        self.is_visible = False

    # -- text fitting ----------------------------------------------------
    def _fit(self, text, fonts, width):
        """Largest font that fits, else the smallest with an ellipsis.

        Bindings vary from "up" to "cmd/keys/text" while the caps they sit on
        are a fixed width, so the text is measured rather than assumed. Tk
        measures in the real rendered font, which is what makes this survive
        both a scaled Windows display and whatever WSLg substitutes.
        """
        for font in fonts:
            if font.measure(text) <= width:
                return text, font
        font = fonts[-1]
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return (text + "…" if text else ""), font

    # -- drawing ---------------------------------------------------------
    def _draw_cap(self, cap, x, y):
        canvas, fonts = self.canvas, self.fonts
        width = cap.width * UNIT - GAP
        height = ROW_HEIGHT - GAP
        fill = CAP_FILL
        if cap.role == "special_key":
            fill = CAP_SPECIAL
        elif cap.role == "structural" and not cap.is_bound:
            fill = CAP_STRUCTURAL
        canvas.create_rectangle(
            x, y, x + width, y + height, fill=fill, outline=CAP_EDGE, width=1
        )
        dim = cap.role == "structural" and not cap.is_bound
        canvas.create_text(
            x + 7,
            y + 5,
            anchor="nw",
            text=cap.label,
            fill=LABEL_DIM if dim else LABEL,
            font=fonts["label"],
        )
        if cap.text:
            text, font = self._fit(cap.text, fonts["binding"], width - 12)
            canvas.create_text(
                x + 7,
                y + 30,
                anchor="nw",
                text=text,
                fill=TEXT_BY_ROLE.get(cap.role, TEXT_BY_ROLE[""]),
                font=font,
            )
        if cap.detail:
            text, font = self._fit(cap.detail, fonts["binding"], width - 12)
            canvas.create_text(
                x + 7, y + 49, anchor="nw", text=text, fill=DETAIL, font=font
            )

    def _draw_tabs(self, active):
        canvas, fonts = self.canvas, self.fonts
        x = PAD
        for name in TABS:
            label = f"  {name}  "
            w = fonts["label"].measure(label) + 8
            if name == active:
                canvas.create_rectangle(
                    x,
                    PAD - 8,
                    x + w,
                    PAD + 22,
                    fill=TAB_ACTIVE_FILL,
                    outline=TAB_ACTIVE_EDGE,
                )
            canvas.create_text(
                x + w / 2,
                PAD + 7,
                text=name,
                fill=LABEL if name == active else LABEL_DIM,
                font=fonts["label"],
            )
            x += w + 6
        canvas.create_text(
            x + 18,
            PAD + 7,
            anchor="w",
            text="←  →  switch tabs        ESC  close",
            fill=HINT,
            font=fonts["header"],
        )

    def _render(self, tab):
        rows = self.build_rows(tab)
        canvas = self.canvas
        canvas.delete("all")
        self._draw_tabs(tab)

        y = PAD + HEADER
        for row in rows:
            x = PAD
            for cap in row:
                self._draw_cap(cap, x, y)
                x += cap.width * UNIT
            y += ROW_HEIGHT

        notes = [
            f"Caps + {name} = {text} {detail}".strip()
            for name, text, detail in self.footer_notes()
        ]
        if notes:
            canvas.create_text(
                PAD,
                y + 10,
                anchor="nw",
                text="not on this board:   " + "     ".join(notes),
                fill=HINT,
                font=self.fonts["header"],
            )

    def _build_fonts(self, root):
        family = "Consolas" if "Consolas" in tkfont.families(root) else "TkFixedFont"
        return {
            "label": tkfont.Font(root=root, family=family, size=12, weight="bold"),
            "header": tkfont.Font(root=root, family=family, size=11),
            "binding": [
                tkfont.Font(root=root, family=family, size=size) for size in (10, 9, 8)
            ],
        }

    # -- lifecycle -------------------------------------------------------
    def show(self, tab=None):
        tab = tab if tab in TABS else self.tab
        if self.is_visible:
            if tab != self.tab:  # same window, new writing on the caps
                self.tab = tab
                self._render(tab)
                self.root.update()
            return
        try:
            width = int(ROW_WIDTH * UNIT) + PAD * 2
            height = ROW_HEIGHT * len(ROWS) + PAD * 2 + HEADER + FOOTER
            root = tk.Tk()
            root.configure(bg=BACKGROUND)
            self.root = root
            self.fonts = self._build_fonts(root)
            self.canvas = tk.Canvas(
                root, bg=BACKGROUND, width=width, height=height, highlightthickness=0
            )
            self.canvas.pack()
            self.tab = tab
            self._render(tab)
            screen_x = (root.winfo_screenwidth() - width) // 2
            screen_y = (root.winfo_screenheight() - height) // 3
            root.geometry(f"{width}x{height}+{max(0, screen_x)}+{max(0, screen_y)}")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            if self.overlay:
                # no focus stealing: DoKey's hook still sees the arrows and ESC,
                # and the user can keep working in whatever was in front
                root.overrideredirect(True)
            else:
                root.title("DoKey keyboard")
                root.bind("<Escape>", lambda event: root.destroy())
                root.bind("<Left>", lambda event: self.step(-1))
                root.bind("<Right>", lambda event: self.step(1))
            root.update()
            self.is_visible = True
        except tk.TclError:
            logger.exception("Could not open the keyboard window")
            self.root = self.canvas = None
            self.is_visible = False

    def step(self, delta):
        """Move to the next or previous tab, wrapping."""
        if not self.is_visible:
            return
        self.show(TABS[(TABS.index(self.tab) + delta) % len(TABS)])

    def clear(self):
        if not self.is_visible:
            return
        try:
            self.root.destroy()
        except tk.TclError:
            logger.exception("Could not close the keyboard window")
        finally:
            # the fonts belong to the root that just died; keeping them would
            # pin a destroyed interpreter and hand stale objects to the redraw
            self.root = self.canvas = self.fonts = None
            self.is_visible = False

    def run_standalone(self, tab=None):
        """Show and block until ESC or the window manager closes it.

        Keeps the mainloop inside the window rather than making callers reach
        for .root - the only place that ever needs it is a preview entrypoint.
        """
        self.show(tab)
        if not self.root:
            return False
        self.root.mainloop()
        self.root = self.canvas = self.fonts = None
        self.is_visible = False
        return True
