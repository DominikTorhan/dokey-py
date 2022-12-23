from typing import List, Optional, Any
from app.current_state import CurrentState, OFF, NORMAL, INSERT
from app.config import Config
from app.events import Event, SendEvent, CMDEvent, DoKeyEvent
from app.modificators import Modificators
from app.keys import Keys


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
        self.state: CurrentState = state

    def process(
        self,
        key: Keys,
        is_key_up=False,
        modifs_os: Modificators = None,
    ) -> Optional[Event]:

        # process CAPSLOCK
        if key.is_caps():
            return self._process_capital(key, is_key_up)

        # process Modificators
        if key.is_modif_ex():
            new_modificators = self._get_next_modificators(key, is_key_up)
            self.state.modificators = new_modificators
            return Event()

        # try update modifiers by OS modifiers. only when non modifier is pressed.
        self._try_update_modifiers_by_os(modifs_os)

        if is_key_up:
            return Event()

        # mode Change
        new_mode, new_prevent_esc_on_caps_up = self._try_process_mode_change(key)
        if new_mode > -1:
            self.state.mode = new_mode
            self.state.prevent_esc_on_caps_up = new_prevent_esc_on_caps_up
            return Event(True)

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

        # caps key
        event = self._process_normal_and_insert_with_capital(key)
        return event

    def _try_process_mode_change(self, key: Keys) -> (Optional[int], bool):
        if self.state.modificators.caps:
            # TODO mode keys in config?
            mode_off_key = Keys.Q
            mode_change_key = Keys.F
            if key == mode_off_key:
                return OFF, True

            if key == mode_change_key:
                return get_next_mode(self.state.mode), True

            return -1, False

        if key.is_esc() and self.state.mode == INSERT:
            return get_prev_mode(self.state.mode), self.state.prevent_esc_on_caps_up

        return -1, False

    def _process_capital(self, key: Keys, is_key_up: bool) -> Event:

        new_prevent_esc_on_caps_up = self.state.prevent_esc_on_caps_up
        new_mode = self.state.mode

        if is_key_up and not new_prevent_esc_on_caps_up and self.state.mode == INSERT:
            new_mode = NORMAL  # prev mode at esc

        if is_key_up and new_prevent_esc_on_caps_up:
            new_prevent_esc_on_caps_up = False

        new_modificators = self._get_next_modificators(
            key, is_key_up
        )  # only for CAPS?!

        self.state.mode = new_mode
        self.state.modificators = new_modificators
        self.state.prevent_esc_on_caps_up = new_prevent_esc_on_caps_up
        return Event(True)

    def _try_process_single_step(self, key: Keys) -> Optional[Event]:
        if self.state.modificators.caps or self.state.modificators.win:
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
        if self.state.modificators.caps or self.state.modificators.win:
            return None

        if self.state.first_step == Keys.NONE:
            return None

        first_step = self.state.first_step
        self.state.first_step = Keys.NONE

        event = self.config.get_two_step_event(first_step, key)
        if event:
            return event

        # event = self.config.get_two_steps_command(first_step, key)
        # if event:
        #     return event

        return Event(True)

    def _process_normal_and_insert_with_capital(self, key: Keys) -> Optional[SendEvent]:
        if self.state.mode == OFF or not self.state.modificators.caps:
            return None
        event = self.config.try_get_caps_send(key)
        if not event:
            return None
        self.state.first_step = Keys.NONE
        self.state.prevent_esc_on_caps_up = True
        return event

    def _get_next_modificators(self, key: Keys, is_key_up: bool) -> Modificators:
        down = not is_key_up
        control = self.state.modificators.control
        shift = self.state.modificators.shift
        alt = self.state.modificators.alt
        win = self.state.modificators.win
        caps = self.state.modificators.caps
        if key.is_control():
            control = down
        if key.is_shift():
            shift = down
        if key.is_alt():
            alt = down
        if key.is_win():
            win = down
        if key.is_caps():
            caps = down

        modificators = Modificators()
        modificators.control = control
        modificators.shift = shift
        modificators.alt = alt
        modificators.win = win
        modificators.caps = caps

        return modificators

    def _try_process_dokey_event(self, key: Keys):
        if not self.state.modificators.caps:
            return None
        if key == Keys.BACKSPACE:  # TODO command to config
            return DoKeyEvent()

    def _try_update_modifiers_by_os(self, modifs_os: Modificators):
        """
        Solution of windows lock win+l. Win is down. We can't receive up event! Modifs_os is additional
        state of modifires.
        """
        if not modifs_os:
            return

        if not modifs_os.win and self.state.modificators.win:
            self.state.modificators.win = False  # for windows lock win+l issue
        if not modifs_os.control and self.state.modificators.control:
            self.state.modificators.control = False
        if not modifs_os.shift and self.state.modificators.shift:
            self.state.modificators.shift = False
        if not modifs_os.alt and self.state.modificators.alt:
            self.state.modificators.alt = False
