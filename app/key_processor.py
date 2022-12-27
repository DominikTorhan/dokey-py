import logging
from typing import List, Optional, Any
from app.app_state import AppState, OFF, NORMAL, INSERT
from app.config import Config
from app.events import Event, SendEvent, CMDEvent, DoKeyEvent, EventLike
from app.modifs import Modifs
from app.keys import Keys


logger = logging.getLogger(__name__)


def get_prev_mode(mode: int) -> int:
    if mode == INSERT or mode == NORMAL:
        return NORMAL
    return OFF


def get_next_mode(mode: int) -> int:
    if mode == INSERT or mode == NORMAL:
        return INSERT
    return NORMAL


class KeyProcessor:
    def __init__(self, config, state):
        self.config: Config = config
        self.state: AppState = state

    def process(
        self,
        key: Keys,
        is_key_up=False,
        modifs_os: Modifs = None,
    ) -> Optional[EventLike]:
        """Side effect: change of AppState!"""

        # process special key (usually caps lock)
        if key == self.config.special_key:
            return self._process_special(is_key_up)

        # process Modifs
        if key.is_modif_ex():
            new_modifs = self._get_next_modifs(key, is_key_up)
            self.state.modifs = new_modifs
            return Event()

        # try update modifiers by OS modifiers. only when non modifier is pressed.
        self._try_update_modifs_by_os(modifs_os)

        # help
        event = self._process_help(key, is_key_up)
        if event:
            return event

        if is_key_up:
            return Event()

        # mode Change
        event = self._try_process_mode_change(key)
        if event:
            return event

        # single step
        event = self._try_process_single_step(key)
        if event:
            return event

        # two-step
        event = self._try_process_two_step(key)
        if event:
            return event

        # command key
        event = self._try_process_dokey_event(key)
        if event:
            return event

        # special key
        event = self._process_normal_and_insert_with_special(key)
        return event

    def _try_process_mode_change(self, key: Keys) -> (Optional[int], bool):
        if not self.state.is_special_down:
            return None

        if key == self.config.off_mode_key:
            self.state.mode = OFF
            self.state.prevent_prev_mode_on_special_up = True
            return Event(True)

        if key == self.config.change_mode_key:
            self.state.mode = get_next_mode(self.state.mode)
            self.state.prevent_prev_mode_on_special_up = True
            return Event(True)

        return None

    def _process_special(self, is_key_up: bool) -> Event:

        if is_key_up and not self.state.prevent_prev_mode_on_special_up and self.state.mode == INSERT:
            self.state.mode = NORMAL  # prev mode at special up

        if is_key_up and self.state.prevent_prev_mode_on_special_up:
            self.state.prevent_prev_mode_on_special_up = False

        self.state.is_special_down = not is_key_up

        return Event(True)

    def _process_help(self, key: Keys, is_key_up: bool) -> Optional[Event]:

        is_help = key == self.config.help_key

        if not is_help:
            return None

        if self.state.is_special_down and not is_key_up:
            self.state.is_help_down = True
            return Event(True)

        if not self.state.is_help_down:
            return None

        if not is_key_up:
            return None

        self.state.is_help_down = False

        return Event(True)

    def _try_process_single_step(self, key: Keys) -> Optional[Event]:
        if self.state.is_special_down or self.state.modifs.win:
            return None
        if self.state.mode != NORMAL:
            return None
        if self.state.first_step != Keys.NONE:
            return None

        if key.is_first_step():
            self.state.first_step = key
            return Event(True)

        return self.config.get_single_step_send_event(key)

    def _try_process_two_step(self, key: Keys) -> Optional[Any]:
        if self.state.mode != NORMAL:
            return None
        if self.state.is_special_down or self.state.modifs.win:
            return None

        if self.state.first_step == Keys.NONE:
            return None

        first_step = self.state.first_step
        self.state.first_step = Keys.NONE

        event = self.config.get_two_step_event(first_step, key)
        if event:
            return event

        # prevent
        return Event(True)

    def _process_normal_and_insert_with_special(self, key: Keys) -> Optional[SendEvent]:
        if self.state.mode == OFF or not self.state.is_special_down:
            return None
        event = self.config.try_get_special_send(key)
        if not event:
            return None
        self.state.first_step = Keys.NONE
        self.state.prevent_prev_mode_on_special_up = True
        return event

    def _get_next_modifs(self, key: Keys, is_key_up: bool) -> Modifs:
        down = not is_key_up
        control = self.state.modifs.control
        shift = self.state.modifs.shift
        alt = self.state.modifs.alt
        win = self.state.modifs.win
        if key.is_control():
            control = down
        if key.is_shift():
            shift = down
        if key.is_alt():
            alt = down
        if key.is_win():
            win = down

        modifs = Modifs()
        modifs.control = control
        modifs.shift = shift
        modifs.alt = alt
        modifs.win = win

        return modifs

    def _try_process_dokey_event(self, key: Keys):
        if not self.state.is_special_down:
            return None
        if key == self.config.exit_key:  # TODO command to config
            return DoKeyEvent()

    def _try_update_modifs_by_os(self, modifs_os: Modifs):
        """
        Solution for windows lock win+l issue. Win is down. We can't receive up event, because machine is locked!
        Modifs_os is additional state of modifires.
        """
        if not modifs_os:
            return

        if not modifs_os.win and self.state.modifs.win:
            self.state.modifs.win = False  # for windows lock win+l issue
        if not modifs_os.control and self.state.modifs.control:
            self.state.modifs.control = False
        if not modifs_os.shift and self.state.modifs.shift:
            self.state.modifs.shift = False
        if not modifs_os.alt and self.state.modifs.alt:
            self.state.modifs.alt = False
