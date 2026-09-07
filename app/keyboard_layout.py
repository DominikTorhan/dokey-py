"""The keyboard the cheat-sheet overlay draws, and what DoKey does to each key.

Pure data and a lookup - no Tk and no Windows API - so the layout is testable
off Windows and the drawing code stays a thin renderer over it.

Only the alphanumeric block is modelled: the function row, the navigation
cluster, the arrows and the numpad are all deliberately absent, because DoKey
binds none of them and the point of the overlay is to show the home-row
remapping in one glance.

The same physical rows are drawn for each tab; only the writing on the caps
changes:

    "special"  what the key does with Caps Lock held - the config "special:"
               section plus the control keys (mode changes, help, exit), which
               take precedence because process() reaches them first
    "common"   what the plain key does in Normal mode - the config "common:"
               section plus the two-step first steps, labelled with how many
               bindings hang off them and of what kind

Everything comes from the live Config, so the overlay always describes the
keymap that is actually loaded, user overrides included.
"""

from typing import List, NamedTuple, Optional

from app.config import Config
from app.events import CMDEvent, WriteEvent
from app.keys import Keys

# Widths are in key units: 1.0 is a letter key, and every row sums to 15.0.
# These are the standard ANSI proportions, which is what makes the picture
# recognisable as a keyboard rather than a grid of boxes.
ROWS = [
    [
        ("backtick", "`", 1.0),
        ("d1", "1", 1.0),
        ("d2", "2", 1.0),
        ("d3", "3", 1.0),
        ("d4", "4", 1.0),
        ("d5", "5", 1.0),
        ("d6", "6", 1.0),
        ("d7", "7", 1.0),
        ("d8", "8", 1.0),
        ("d9", "9", 1.0),
        ("d0", "0", 1.0),
        ("minus", "-", 1.0),
        ("equal", "=", 1.0),
        ("backspace", "Backspace", 2.0),
    ],
    [
        ("tab", "Tab", 1.5),
        ("q", "Q", 1.0),
        ("w", "W", 1.0),
        ("e", "E", 1.0),
        ("r", "R", 1.0),
        ("t", "T", 1.0),
        ("y", "Y", 1.0),
        ("u", "U", 1.0),
        ("i", "I", 1.0),
        ("o", "O", 1.0),
        ("p", "P", 1.0),
        ("square_bracket_open", "[", 1.0),
        ("square_bracket_close", "]", 1.0),
        ("backslash", "\\", 1.5),
    ],
    [
        ("capital", "Caps", 1.75),
        ("a", "A", 1.0),
        ("s", "S", 1.0),
        ("d", "D", 1.0),
        ("f", "F", 1.0),
        ("g", "G", 1.0),
        ("h", "H", 1.0),
        ("j", "J", 1.0),
        ("k", "K", 1.0),
        ("l", "L", 1.0),
        ("semicolon", ";", 1.0),
        ("apostrophe", "'", 1.0),
        ("enter", "Enter", 2.25),
    ],
    [
        ("shift", "Shift", 2.25),
        ("z", "Z", 1.0),
        ("x", "X", 1.0),
        ("c", "C", 1.0),
        ("v", "V", 1.0),
        ("b", "B", 1.0),
        ("n", "N", 1.0),
        ("m", "M", 1.0),
        ("comma", ",", 1.0),
        ("period", ".", 1.0),
        ("slash", "/", 1.0),
        ("right shift", "Shift", 2.75),
    ],
    [
        ("ctrl", "Ctrl", 1.25),
        ("win", "Win", 1.25),
        ("alt", "Alt", 1.25),
        ("space", "", 6.25),
        ("right alt", "Alt", 1.25),
        (None, "Win", 1.25),
        ("menu", "Menu", 1.25),
        ("right ctrl", "Ctrl", 1.25),
    ],
]

ROW_WIDTH = 15.0

# Keys that are part of the machinery rather than things DoKey remaps. They are
# drawn dimmer so the eye lands on the letters that actually carry bindings.
STRUCTURAL = {
    "tab",
    "backspace",
    "enter",
    "shift",
    "right shift",
    "ctrl",
    "right ctrl",
    "alt",
    "right alt",
    "win",
    "right windows",
    "menu",
    "space",
}


class KeyCap(NamedTuple):
    """One drawn key: its engraving, its size, and what it does in this tab.

    key is None for a cap DoKey has no name for - the right Windows key is on
    the board but not in the Keys map, and a cap it cannot name is a cap it can
    never bind.

    text is the binding; detail is the dimmer second line, used where one line
    cannot say it - "mouse"/"mode" for a control key, or how many bindings sit
    behind a first step and whether they are keys, commands or text.
    """

    label: str
    width: float
    key: Optional[Keys]
    text: str
    detail: str
    role: str  # "", "structural", "special_key", "control", "prefix"

    @property
    def is_bound(self) -> bool:
        return bool(self.text)


# A one-unit cap holds about seven characters; "ctrl+shift+tab" is fourteen and
# truncates to nonsense. Modifiers collapse to the single letters the vim-style
# notation DoKey already borrows from uses, and the few long key names take
# their usual short forms, so even a three-part chord fits whole.
MODIFIER_SHORT = {
    "ctrl": "C",
    "right ctrl": "C",
    "shift": "S",
    "lshiftkey": "S",
    "right shift": "S",
    "alt": "A",
    "alt gr": "A",
    "right alt": "A",
    "win": "W",
    "windows": "W",
    "left windows": "W",
}

KEY_SHORT = {
    "backspace": "bksp",
    "page down": "pgdn",
    "page up": "pgup",
    "escape": "esc",
    "insert": "ins",
    "print screen": "prtsc",
    "print_screen": "prtsc",
    "square_bracket_open": "[",
    "square_bracket_close": "]",
    "apostrophe": "'",
    "semicolon": ";",
    "backslash": "\\",
    "backtick": "`",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "minus": "-",
    "equal": "=",
}


def _name(key: Keys) -> str:
    try:
        return key.to_string()
    except ValueError:
        # a Keys member with no name in the map: show the enum rather than crash
        return key.name.lower()


def describe(send: Optional[List[Keys]]) -> str:
    """Compact form of a binding: "C-S-tab", "bksp", "up end enter".

    Chord parts join with "-", successive chords with a space. Long enough to
    read at a glance, short enough not to be cut off.
    """
    if not send:
        return ""
    chords, held = [], []
    for key in send:
        name = _name(key)
        if key.is_modif_ex():
            held.append(MODIFIER_SHORT.get(name, name))
            continue
        held.append(KEY_SHORT.get(name, name))
        chords.append("-".join(held))
        held = []
    if held:  # binding that is only modifiers, e.g. a bare "win"
        chords.append("-".join(held))
    return " ".join(chords)


TABS = ("special", "common")


def _controls(config):
    """Caps-held keys handled by process() before the "special:" section.

    Order matters here the same way it does in KeyProcessor: help, diagnostics
    and the cheat-sheet key are reached first, then the mode keys in
    _try_process_mode_change's own order (off, change, mouse), then exit and
    clear-screen. Anything in this map wins over a "special:" entry on the same
    key, and setdefault keeps the first writer - so if two controls are bound to
    one key, the overlay names the same winner the code picks.
    """
    described = [
        (config.help_key, "help", ""),
        (config.diagnostic_key, "diag", "overlay"),
        (config.keyboard_key, "keys", "this sheet"),
        (config.off_mode_key, "off", "mode"),
        (config.change_mode_key, "mode", "next"),
        (config.mouse_mode_key, "mouse", "mode"),
        (config.exit_key, "exit", "DoKey"),
        (config.clear_screen_key, "clear", "screen"),
    ]
    controls = {}
    for key, text, detail in described:
        if key is not None and key != Keys.NONE:
            controls.setdefault(key, (text, detail))
    return controls


def _prefix_detail(config, key):
    """How many two-step bindings hang off a first step, and of what kind."""
    entries = config.two_step_events.get(key) or {}
    kinds = set()
    for event in entries.values():
        if isinstance(event, CMDEvent):
            kinds.add("cmd")
        elif isinstance(event, WriteEvent):
            kinds.add("text")
        else:
            kinds.add("keys")
    if not kinds:
        return len(entries), "empty"
    # "cmd/keys/text" is wider than a cap; two kinds still fit, three do not,
    # and the point is only to tell a plain remap prefix from one that runs
    # commands or types text
    detail = "/".join(sorted(kinds)) if len(kinds) <= 2 else "mixed"
    return len(entries), detail


def placed_keys():
    """Every key that has a cap on this board."""
    return {
        Keys.from_string(name)
        for row in ROWS
        for name, _, _ in row
        if name is not None
    }


def unplaced_controls(config: Config):
    """Control keys with no cap to write on, as (key name, text, detail).

    Escape is the usual one: it is the exit key, but it lives in the function
    row this layout deliberately leaves out. Rather than bend the keyboard to
    fit it, the drawing lists these under the board.
    """
    placed = placed_keys()
    found = []
    for key, (text, detail) in _controls(config).items():
        if key in placed:
            continue
        name = KEY_SHORT.get(_name(key), _name(key))
        found.append((name, text, detail))
    return sorted(found)


def build(config: Config, tab: str = TABS[0]) -> List[List[KeyCap]]:
    """Resolve the static layout against a loaded Config, for one tab."""
    if tab not in TABS:
        raise ValueError(f"unknown tab {tab!r}, expected one of {TABS}")
    controls = _controls(config) if tab == "special" else {}
    rows = []
    for row in ROWS:
        caps = []
        for name, label, width in row:
            key = Keys.from_string(name) if name else None
            text, detail, role = "", "", ""
            if name is None or name in STRUCTURAL:
                role = "structural"
            if key is not None and key == config.special_key:
                text, detail, role = "DoKey", "special key", "special_key"
            elif key in controls:
                text, detail = controls[key]
                role = "control"
            elif tab == "special":
                text = describe(config.special.get(key))
            elif key is not None and key.is_first_step():
                count, kinds = _prefix_detail(config, key)
                text, detail, role = f"\u25b8 {count}", kinds, "prefix"
            else:
                text = describe(config.common.get(key))
            caps.append(
                KeyCap(
                    label=label,
                    width=width,
                    key=key,
                    text=text,
                    detail=detail,
                    role=role,
                )
            )
        rows.append(caps)
    return rows
