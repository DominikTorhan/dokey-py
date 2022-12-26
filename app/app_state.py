from app.keys import Keys
from app.modificators import Modificators

OFF: int = 0
NORMAL: int = 1
INSERT: int = 2


class AppState:
    def __init__(self):
        """prevent_esc_on_caps_up is needed for case when using caps in Insert mode e.g. Caps+h as backspace. After that we don't want to change mode to Normal"""
        self.modificators: Modificators = Modificators()
        self.prevent_esc_on_caps_up: bool = False
        self.mode: int = NORMAL
        self.first_step: Keys = Keys.NONE
