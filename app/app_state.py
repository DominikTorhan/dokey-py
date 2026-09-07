from app.keys import Keys
from app.modifs import Modifs

OFF: int = 0
NORMAL: int = 1
INSERT: int = 2
MOUSE: int = 3


class AppState:
    def __init__(self):
        """prevent_prev_mode_on_special_up is needed for case when using special key in Insert mode e.g. special+h as backspace. After that we don't want to change mode to Normal"""
        self.modifs: Modifs = Modifs()
        self.prevent_prev_mode_on_special_up: bool = False
        self.is_special_down: bool = False
        self.is_help_down: bool = False
        self.mode: int = NORMAL
        self.first_step: Keys = Keys.NONE
        self.diagnostic_active = False
        self.keyboard_active = False
        # index into app.keyboard_layout.TABS; an int keeps AppState free of
        # any dependency on the drawing side
        self.keyboard_tab: int = 0
