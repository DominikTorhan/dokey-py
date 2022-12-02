from typing import List
from enum import Enum


class Keys(Enum):

    Q = 10
    W = 11
    E = 12
    R = 13
    T = 14
    Y = 15
    U = 16
    I = 17
    O = 18
    P = 19

    A = 20
    S = 21
    D = 22
    F = 23
    G = 24
    H = 25
    J = 26
    K = 27
    L = 28

    Z = 29
    X = 30
    C = 31
    V = 32
    B = 33
    N = 34
    M = 35
    PERIOD = 7
    COMMA = 6
    QUESTION = 63
    WIN = 5
    CTRL = 4
    SHIFT = 3
    ALT = 2
    NONE = 0
    CAPS = 9
    ESC = 1
    ENTER = 50
    BACKSPACE = 51
    INSERT = 52
    HOME = 53
    PAGE_UP = 54
    PAGE_DOWN = 55
    DELETE = 56
    END = 57
    TAB = 58
    LEFT = 59
    RIGHT = 60
    DOWN = 61
    UP = 62
    SPACE = 63
    MENU = 64

    F1 = 81
    F2 = 82
    F3 = 83
    F4 = 84
    F5 = 85
    F6 = 86
    F7 = 87
    F8 = 88
    F9 = 89
    F10 = 90
    F11 = 91
    F12 = 92

    D0 = 100
    D1 = 101
    D2 = 102
    D3 = 103
    D4 = 104
    D5 = 105
    D6 = 106
    D7 = 107
    D8 = 108
    D9 = 109

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
        print("ERROR", self)
        raise ValueError

    def is_modif(self):
        return self in [Keys.CTRL, Keys.ALT, Keys.SHIFT]  # send no win, caps


keyboard_to_dokey_map = {
    "caps lock": Keys.CAPS,
    "capital": Keys.CAPS,
    # mod
    "alt": Keys.ALT,
    "alt gr": Keys.ALT,
    "right alt": Keys.ALT,
    "shift": Keys.SHIFT,
    "right shift": Keys.SHIFT,
    "lshiftkey": Keys.SHIFT,
    "ctrl": Keys.CTRL,
    "right ctrl": Keys.CTRL,
    "windows": Keys.WIN,
    "left windows": Keys.WIN,
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
    ".": Keys.PERIOD,
    "comma": Keys.COMMA,
    "period": Keys.PERIOD,
}


def string_to_multi_keys(s: str) -> []:
    result = []
    steps = s.split(",")
    for st in steps:
        result.extend(st.split("+"))
    return list(map(Keys.from_string, result))


# send(57)
# send('ctrl+alt+del')
# send('alt+F4, enter')
# send('shift+s')
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
