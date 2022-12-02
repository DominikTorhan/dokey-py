from app.enums import Keys

FIRST_STEPS = [Keys.Q, Keys.W, Keys.E, Keys.R, Keys.T, Keys.A, Keys.S, Keys.D, Keys.F, Keys.G, Keys.B, Keys.U, Keys.I]

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
    Keys.QUESTION,
]


class InputKey:
    def __int__(self):
        self.key: Keys = Keys.NONE
        self.is_control: bool = False
        self.is_shift: bool = False
        self.is_alt: bool = False
        self.is_win: bool = False
        self.is_caps: bool = False
        self.is_modif: bool = False
        self.is_esc: bool = False
        self.is_letter_or_digit: bool = False
        self.is_first_step: bool = False

    def __repr__(self):
        return f"Input key: {self.key}"

    @classmethod
    def from_string(cls, key: Keys) -> "InputKey":
        assert isinstance(key, Keys)
        input_key = cls()
        input_key.key: Keys = key
        input_key.is_control = key == Keys.CTRL
        input_key.is_shift = key == Keys.SHIFT
        input_key.is_alt = key == Keys.ALT
        input_key.is_win = key == Keys.WIN
        input_key.is_caps = key == Keys.CAPS
        input_key.is_modif = (
            input_key.is_control
            or input_key.is_shift
            or input_key.is_alt
            or input_key.is_win
            or input_key.is_caps
        )
        input_key.is_esc = key == Keys.ESC
        input_key.is_letter_or_digit = key in LETTER_OR_DIGIT
        input_key.is_first_step = key in FIRST_STEPS
        return input_key
