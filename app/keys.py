from typing import List
from enum import Enum


class Keys(Enum):
    """

    matches to win_32 VK_CODE

    http://pinvoke.net/default.aspx/user32.GetKeyboardState
    """

    NONE = 0
    BACKSPACE = 8
    TAB = 9
    ENTER = 13  # also numpad enter

    SHIFT = 16  # shift 0x10
    CONTROL = 17  # ctrl 0x11
    ALT = 18  # aka menu
    PAUSE = 19
    CAPS = 20

    ESC = 27

    SPACE = 32
    PAGE_UP = 33
    PAGE_DOWN = 34
    END = 35
    HOME = 36
    LEFT = 37
    UP = 38
    RIGHT = 39
    DOWN = 40

    INSERT = 45
    DELETE = 46

    D0 = 48
    D1 = 49
    D2 = 50
    D3 = 51
    D4 = 52
    D5 = 53
    D6 = 54
    D7 = 55
    D8 = 56
    D9 = 57

    A = 65  # 0x41
    B = 66
    C = 67
    D = 68
    E = 69
    F = 70
    G = 71
    H = 72
    I = 73
    J = 74
    K = 75
    L = 76
    M = 77
    N = 78
    O = 79
    P = 80
    Q = 81
    R = 82
    S = 83
    T = 84
    U = 85
    V = 86
    W = 87
    X = 88
    Y = 89
    Z = 90

    LEFT_WIN = 91
    RIGHT_WIN = 92
    MENU = 93

    F1 = 112
    F2 = 113
    F3 = 114
    F4 = 115
    F5 = 116
    F6 = 117
    F7 = 118
    F8 = 119
    F9 = 120
    F10 = 121
    F11 = 122
    F12 = 123

    LEFT_SHIFT = 160
    RIGHT_SHIFT = 161
    LEFT_CTRL = 162
    RIGHT_CTRL = 163
    LEFT_ALT = 164
    RIGHT_ALT = 165

    SEMICOLON = 186  # ; oem_1
    EQUAL = 187  # =
    COMMA = 188  # ,
    MINUS = 189  # -
    PERIOD = 190  # .
    SLASH = 191  # / oem_2
    BACKTICK = 192  # ` oem_3

    SQUARE_BRACKET_OPEN = 219  # [ oem_4
    BACKSLASH = 220  # \ oem_5
    SQUARE_BRACKET_CLOSE = 221  # ] oem_6
    APOSTROPHE = 222  # ' oem_7

    # command
    COMMAND_EXIT = -1

    @staticmethod
    def from_string(s: str) -> "Keys":
        if not s:
            return Keys.NONE
        key = keyboard_to_dokey_map.get(s.strip())
        if not key:
            x = "xxx"
        return key

    def to_string(self) -> str:
        for item in keyboard_to_dokey_map.items():
            if item[1] == self:
                return item[0]
        if self == Keys.NONE:
            return ""
        raise ValueError

    def is_esc(self):
        return self in [Keys.ESC]

    def is_control(self):
        return self in [Keys.RIGHT_CTRL, Keys.LEFT_CTRL]

    def is_shift(self):
        return self in [Keys.RIGHT_SHIFT, Keys.LEFT_SHIFT]

    def is_alt(self):
        return self in [Keys.RIGHT_ALT, Keys.LEFT_ALT]

    def is_win(self):
        return self in [Keys.RIGHT_WIN, Keys.LEFT_WIN]

    def is_caps(self):
        return self in [Keys.CAPS]

    def is_modif(self):
        """Ctrl, alt or shift"""
        return self.is_control() or self.is_alt() or self.is_shift()

    def is_modif_ex(self):
        """Ctrl, alt, shift, win or caps"""
        return (
            self.is_control()
            or self.is_alt()
            or self.is_shift()
            or self.is_win()
            or self.is_caps()
        )

    def is_first_step(self):
        return self in FIRST_STEPS

    def is_letter_or_digit(self):
        return self in LETTER_OR_DIGIT


FIRST_STEPS = [
    Keys.Q,
    Keys.W,
    Keys.E,
    Keys.R,
    Keys.T,
    Keys.A,
    Keys.S,
    Keys.D,
    Keys.F,
    Keys.G,
    Keys.B,
    Keys.U,
    Keys.I,
]

LETTER_OR_DIGIT = [
    Keys.Q,
    Keys.W,
    Keys.E,
    Keys.R,
    Keys.T,
    Keys.Y,
    Keys.U,
    Keys.I,
    Keys.O,
    Keys.P,
    Keys.A,
    Keys.S,
    Keys.D,
    Keys.F,
    Keys.G,
    Keys.H,
    Keys.J,
    Keys.K,
    Keys.L,
    Keys.Z,
    Keys.X,
    Keys.C,
    Keys.V,
    Keys.B,
    Keys.N,
    Keys.M,
    Keys.D1,
    Keys.D2,
    Keys.D3,
    Keys.D4,
    Keys.D5,
    Keys.D6,
    Keys.D7,
    Keys.D8,
    Keys.D9,
    Keys.D0,
    Keys.F1,
    Keys.F2,
    Keys.F3,
    Keys.F4,
    Keys.F5,
    Keys.F6,
    Keys.F7,
    Keys.F8,
    Keys.F9,
    Keys.F10,
    Keys.F11,
    Keys.F12,
    Keys.COMMA,
    Keys.PERIOD,
]


keyboard_to_dokey_map = {
    "COMMAND_EXIT": Keys.COMMAND_EXIT,
    "caps lock": Keys.CAPS,
    "capital": Keys.CAPS,
    # mod
    "alt": Keys.LEFT_ALT,
    "alt gr": Keys.RIGHT_ALT,
    "right alt": Keys.RIGHT_ALT,
    "shift": Keys.LEFT_SHIFT,
    "right shift": Keys.RIGHT_SHIFT,
    "lshiftkey": Keys.LEFT_SHIFT,
    "ctrl": Keys.LEFT_CTRL,
    "right ctrl": Keys.RIGHT_CTRL,
    "windows": Keys.LEFT_WIN,
    "left windows": Keys.LEFT_WIN,
    "win": Keys.LEFT_WIN,
    # com
    "esc": Keys.ESC,
    "escape": Keys.ESC,
    "space": Keys.SPACE,
    "enter": Keys.ENTER,
    "backspace": Keys.BACKSPACE,
    "del": Keys.DELETE,
    "home": Keys.HOME,
    "end": Keys.END,
    "page down": Keys.PAGE_DOWN,
    "page up": Keys.PAGE_UP,
    "tab": Keys.TAB,
    "left": Keys.LEFT,
    "right": Keys.RIGHT,
    "down": Keys.DOWN,
    "up": Keys.UP,
    "menu": Keys.MENU,
    # func
    "f1": Keys.F1,
    "f2": Keys.F2,
    "f3": Keys.F3,
    "f4": Keys.F4,
    "f5": Keys.F5,
    "f6": Keys.F6,
    "f7": Keys.F7,
    "f8": Keys.F8,
    "f9": Keys.F9,
    "f10": Keys.F10,
    "f11": Keys.F11,
    "f12": Keys.F12,
    # nums
    "1": Keys.D1,
    "2": Keys.D2,
    "3": Keys.D3,
    "4": Keys.D4,
    "5": Keys.D5,
    "6": Keys.D6,
    "7": Keys.D7,
    "8": Keys.D8,
    "9": Keys.D9,
    "0": Keys.D0,
    "d1": Keys.D1,
    "d2": Keys.D2,
    "d3": Keys.D3,
    "d4": Keys.D4,
    "d5": Keys.D5,
    "d6": Keys.D6,
    "d7": Keys.D7,
    "d8": Keys.D8,
    "d9": Keys.D9,
    "d0": Keys.D0,
    "q": Keys.Q,
    "w": Keys.W,
    "e": Keys.E,
    "r": Keys.R,
    "t": Keys.T,
    "y": Keys.Y,
    "u": Keys.U,
    "i": Keys.I,
    "o": Keys.O,
    "p": Keys.P,
    "a": Keys.A,
    "s": Keys.S,
    "d": Keys.D,
    "f": Keys.F,
    "g": Keys.G,
    "h": Keys.H,
    "j": Keys.J,
    "k": Keys.K,
    "l": Keys.L,
    "z": Keys.Z,
    "x": Keys.X,
    "c": Keys.C,
    "v": Keys.V,
    "b": Keys.B,
    "n": Keys.N,
    "m": Keys.M,
    ",": Keys.COMMA,
    "comma": Keys.COMMA,
    ".": Keys.PERIOD,
    "period": Keys.PERIOD,
    ";": Keys.SEMICOLON,
    "semicolon": Keys.SEMICOLON,
    "'": Keys.APOSTROPHE,
    "apostrophe": Keys.APOSTROPHE,
    "-": Keys.MINUS,
    "minus": Keys.MINUS,
    "=": Keys.EQUAL,
    "equal": Keys.EQUAL,
    "/": Keys.SLASH,
    "slash": Keys.SLASH,
    "\\": Keys.BACKSLASH,
    "backslash": Keys.BACKSLASH,
    "`": Keys.BACKTICK,
    "backtick": Keys.BACKTICK,
    "[": Keys.SQUARE_BRACKET_OPEN,
    "square_bracket_open": Keys.SQUARE_BRACKET_OPEN,
    "]": Keys.SQUARE_BRACKET_CLOSE,
    "square_bracket_close": Keys.SQUARE_BRACKET_CLOSE,
}

control_keys = [Keys.CONTROL, Keys.LEFT_CTRL, Keys.RIGHT_CTRL]
shift_keys = [Keys.SHIFT, Keys.LEFT_SHIFT, Keys.RIGHT_SHIFT]
alt_keys = [Keys.ALT, Keys.LEFT_ALT, Keys.RIGHT_ALT]
win_keys = [Keys.LEFT_WIN, Keys.RIGHT_WIN]


def string_to_multi_keys(s: str) -> []:
    result = []
    steps = s.split(",")
    for st in steps:
        result.extend(st.split("+"))
    return list(map(Keys.from_string, result))


def keys_to_send(keys: List[Keys]) -> str:
    send = ""
    for key in keys:
        send += key.to_string()
        if key.is_modif():
            send += "+"
        else:
            send += ","
    send = send.rstrip(",")
    return send
