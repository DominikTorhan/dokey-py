from typing import List, Optional
from app.app_state import AppState, OFF, NORMAL, INSERT
from app.config import Config
from app.modificators import Modificators
from app.keys import Keys


def get_prev_state(state: int) -> int:
    if state == INSERT or state == NORMAL:
        return NORMAL
    return OFF


def get_next_state(state: int) -> int:
    if state == INSERT or state == NORMAL:
        return INSERT
    return NORMAL


class Result:
    def __init__(self):
        self.app_state: AppState = None
        self.send: List[Keys] = []
        self.cmd = ""
        self.prevent_key_process: bool = False

    def __repr__(self):
        return f"Send: {self.send} AppState: {self.app_state} Prev: {self.prevent_key_process}"


class KeyProcessor:
    def __init__(self):
        self.config: Config = None
        self.app_state: AppState = None

    def process(self, key: Keys, is_key_up=False, modifs_os: Modificators = None) -> Result:
        assert isinstance(self.app_state.first_step, Keys)
        # process CAPSLOCK
        if key.is_caps():
            return self.process_capital(key, is_key_up)
        # process Modificators
        if key.is_modif_ex():
            return self.process_modificators(key, is_key_up)

        # try update modifiers by OS modifiers. only when non modifier is pressed.
        self.try_update_modifiers_by_os(modifs_os)

        if is_key_up:
            return self.create_result_with_app_state(self.app_state)

        # stateChange
        app_state = self.try_process_state_change(key)
        if app_state is not None:
            return self.create_result_with_app_state(app_state, True)

        # single step
        result = self.try_process_single_step(key)
        if result is not None:
            return result

        # two-step
        result = self.try_process_two_step(key)
        if result is not None:
            return result

        # command key
        result = self.try_process_command_key(key)
        if result is not None:
            return result

        # caps key
        result = self.process_normal_and_insert_with_capital(key)
        return result

    def try_process_state_change(self, key) -> AppState:
        if self.app_state.modificators.caps:
            # TODO mode keys in config?
            mode_off_key = Keys.Q
            mode_change_key = Keys.F
            if key == mode_off_key:
                app_state = AppState()
                app_state.state = OFF
                app_state.prevent_esc_on_caps_up = True
                app_state.modificators = self.app_state.modificators
                return app_state

            if key == mode_change_key:
                app_state = AppState()
                app_state.state = get_next_state(self.app_state.state)
                app_state.prevent_esc_on_caps_up = True
                app_state.modificators = self.app_state.modificators
                return app_state

            return None

        if key.is_esc() and self.app_state.state == INSERT:
            app_state = AppState()
            app_state.state = get_prev_state(self.app_state.state)
            app_state.modificators = self.app_state.modificators
            app_state.prevent_esc_on_caps_up = self.app_state.prevent_esc_on_caps_up
            return app_state

        return None

    def process_capital(self, key: Keys, is_key_up: bool) -> Result:
        prevent_esc_on_caps_up = self.app_state.prevent_esc_on_caps_up
        state = self.app_state.state
        if is_key_up and not prevent_esc_on_caps_up and state == INSERT:
            state = NORMAL  # prev state at esc
        if is_key_up and prevent_esc_on_caps_up:
            prevent_esc_on_caps_up = False
        modificators = self.get_next_modificators(key, is_key_up)  # only for CAPS?!
        result = self.create_result(
            state, Keys.NONE, prevent_esc_on_caps_up, modificators, True
        )
        return result

    def process_modificators(self, key: Keys, is_key_up: bool) -> Result:
        modificators = self.get_next_modificators(key, is_key_up)
        result = self.create_result(
            self.app_state.state,
            self.app_state.first_step,
            self.app_state.prevent_esc_on_caps_up,
            modificators,
        )
        return result

    def try_process_single_step(self, key: Keys) -> Optional[Result]:
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None
        if self.app_state.state != NORMAL:
            return None
        if self.app_state.first_step != Keys.NONE:
            return None
        result = self.try_process_first_step(key)
        if result:
            return result
        if key.is_first_step():
            return None

        send = self.config.common.get(key)
        if not send:
            return None
        return self.create_result_with_app_state(self.app_state, True, send)

    def try_process_two_step(self, key: Keys) -> Optional[Result]:
        if self.app_state.state != NORMAL:
            return None
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None

        if self.app_state.first_step == Keys.NONE:
            return None

        send = self.config.try_get_two_key_send(
            self.app_state.first_step, key
        )
        cmd = ""
        if not send or send == [None]:
            cmd = self.config.try_get_two_key_command(
                self.app_state.first_step, key
            )
        result = self.create_result(
            self.app_state.state,
            Keys.NONE,
            self.app_state.prevent_esc_on_caps_up,
            self.app_state.modificators,
            True,
            send,
            cmd=cmd,
        )
        return result

    def try_process_first_step(self, key: Keys) -> Optional[Result]:
        if self.app_state.first_step != Keys.NONE or not key.is_first_step():
            return None
        result = self.create_result(
            self.app_state.state,
            key,
            self.app_state.prevent_esc_on_caps_up,
            self.app_state.modificators,
            key.is_letter_or_digit(),
        )
        return result

    def process_normal_and_insert_with_capital(self, key: Keys) -> Optional[Result]:
        if self.app_state.state == OFF or not self.app_state.modificators.caps:
            return None
        send = self.config.try_get_caps_send(key)
        if not send:
            return None
        result = self.create_result(
            self.app_state.state,
            Keys.NONE,
            True,
            self.app_state.modificators,
            True,
            send,
        )
        return result

    def create_result(
        self,
        state,
        first_step: Keys,
        prevent_esc_on_caps_up,
        modificators,
        prevent_key_process=False,
        send: List[Keys] = [],
        cmd: str = "",
    ) -> Result:
        app_state = AppState()
        app_state.state = state
        app_state.first_step = first_step
        app_state.prevent_esc_on_caps_up = prevent_esc_on_caps_up
        app_state.modificators = modificators
        result = Result()
        result.app_state = app_state
        result.send = send
        result.prevent_key_process = prevent_key_process
        result.cmd = cmd
        return result

    def create_result_with_app_state(
        self, app_state, prevent_key_process=False, send: List[Keys] = []
    ) -> Result:
        result = Result()
        result.app_state = app_state
        result.send = send
        result.prevent_key_process = prevent_key_process
        return result

    def get_next_modificators(self, key: Keys, is_key_up: bool) -> Modificators:
        down = not is_key_up
        control = self.app_state.modificators.control
        shift = self.app_state.modificators.shift
        alt = self.app_state.modificators.alt
        win = self.app_state.modificators.win
        caps = self.app_state.modificators.caps
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

    def try_process_command_key(self, key: Keys):
        if not self.app_state.modificators.caps:
            return None
        if key == Keys.BACKSPACE:  # TODO command to config
            return self.create_result_with_app_state(
                self.app_state, True, [Keys.COMMAND_EXIT]
            )

    def try_update_modifiers_by_os(self, modifs_os: Modificators):
        if not modifs_os:
            return

        if not modifs_os.win and self.app_state.modificators.win:
            print("WIN OFF by OS")  # for windows lock win+l issue
            self.app_state.modificators.win = False
        if not modifs_os.control and self.app_state.modificators.control:
            self.app_state.modificators.control = False
        if not modifs_os.shift and self.app_state.modificators.shift:
            self.app_state.modificators.shift = False
        if not modifs_os.alt and self.app_state.modificators.alt:
            self.app_state.modificators.alt = False
