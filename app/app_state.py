from app.enums import Keys
from app.modificators import Modificators

OFF: int = 0
NORMAL: int = 1
INSERT: int = 2


def get_prev_state(state: int) -> int:
    if state == INSERT or state == NORMAL:
        return NORMAL
    return OFF


def get_next_state(state: int) -> int:
    if state == INSERT or state == NORMAL:
        return INSERT
    return NORMAL


class AppState:
    def __init__(self):
        self.state: int = NORMAL
        self.first_step: Keys = Keys.NONE
        self.prevent_esc_on_caps_up: bool = False
        self.modificators: Modificators = Modificators()

    def __repr__(self) -> str:
        return self.to_string()

    def to_string(self) -> str:
        prev = "*" if self.prevent_esc_on_caps_up else ""

        s = f"{str(self.state)},{self.first_step.to_string()},{self.modificators.to_string()}{prev}"
        return s
