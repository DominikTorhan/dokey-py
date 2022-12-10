from typing import List
from app.app_state import AppState, OFF, NORMAL, INSERT, get_next_state, get_prev_state
from app.input_key import InputKey
from app.config import Config
from app.modificators import Modificators
from app.enums import Keys


class Result:
    def __init__(self):
        self.app_state: AppState = None
        self.send: List[Keys] = []
        self.prevent_key_process: bool = False

    def __repr__(self):
        return f"Send: {self.send} AppState: {self.app_state} Prev: {self.prevent_key_process}"


class Processor:
    def __init__(self):
        self.config: Config = None
        self.is_key_up: bool = False
        self.input_key: InputKey = None
        self.app_state: AppState = None

    def __repr__(self):
        return f"AppState: {repr(self.app_state)}, InputKey: {repr(self.input_key)} isUp: {self.is_key_up}"

    def process(self, modifs_os: Modificators = None) -> Result:
        assert isinstance(self.app_state.first_step, Keys)
        # process CAPSLOCK
        if self.input_key.is_caps:
            return self.process_capital()
        # process Modificators
        if self.input_key.is_modif:
            return self.process_modificators()

        # try update modifiers by OS modifiers. only when non modifier is pressed.
        self.try_update_modifiers_by_os(modifs_os)

        if self.is_key_up:
            return self.create_result_with_app_state(self.app_state, [], False)

        # stateChange
        app_state = self.try_process_state_change()
        if app_state is not None:
            return self.create_result_with_app_state(app_state, [], True)

        # single step
        result = self.try_process_single_step()
        if result is not None:
            return result

        # two-step
        result = self.try_process_two_step()
        if result is not None:
            return result

        # command key
        result = self.try_process_command_key()
        if result is not None:
            return result

        # caps key
        result = self.process_normal_and_insert_with_capital()
        return result

    def try_process_state_change(self) -> AppState:
        if self.app_state.modificators.caps:
            # TODO mode keys in config?
            mode_off_key = Keys.Q
            mode_change_key = Keys.F
            if self.input_key.key == mode_off_key:
                app_state = AppState()
                app_state.state = OFF
                app_state.prevent_esc_on_caps_up = True
                app_state.modificators = self.app_state.modificators
                return app_state

            if self.input_key.key == mode_change_key:
                app_state = AppState()
                app_state.state = get_next_state(self.app_state.state)
                app_state.prevent_esc_on_caps_up = True
                app_state.modificators = self.app_state.modificators
                return app_state

            return None

        if self.input_key.is_esc and self.app_state.state == INSERT:
            app_state = AppState()
            app_state.state = get_prev_state(self.app_state.state)
            app_state.modificators = self.app_state.modificators
            app_state.prevent_esc_on_caps_up = self.app_state.prevent_esc_on_caps_up
            return app_state

        return None

    def process_capital(self) -> Result:
        prevent_esc_on_caps_up = self.app_state.prevent_esc_on_caps_up
        state = self.app_state.state
        if self.is_key_up and not prevent_esc_on_caps_up and state == INSERT:
            state = NORMAL  # prev state at esc
        if self.is_key_up and prevent_esc_on_caps_up:
            prevent_esc_on_caps_up = False
        modificators = self.get_next_modificators()  # only for CAPS?!
        result = self.create_result(
            state, Keys.NONE, prevent_esc_on_caps_up, modificators, [], True
        )
        return result

    def process_modificators(self) -> Result:
        modificators = self.get_next_modificators()
        result = self.create_result(
            self.app_state.state,
            self.app_state.first_step,
            self.app_state.prevent_esc_on_caps_up,
            modificators,
            [],
            False,
        )
        return result

    def try_process_single_step(self) -> Result:
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None
        if self.app_state.state != NORMAL:
            return None
        if self.app_state.first_step != Keys.NONE:
            return None
        result = self.try_process_first_step()
        if result:
            return result
        if self.input_key.is_first_step:
            return None

        send = self.config.common.get(self.input_key.key)
        if not send:
            return None
        return self.create_result_with_app_state(self.app_state, send, True)

    def try_process_two_step(self) -> Result:
        if self.app_state.state != NORMAL:
            return None
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None

        if self.app_state.first_step == Keys.NONE:
            return None

        send = self.config.try_get_two_key_send(
            self.app_state.first_step, self.input_key.key
        )
        result = self.create_result(
            self.app_state.state,
            Keys.NONE,
            self.app_state.prevent_esc_on_caps_up,
            self.app_state.modificators,
            send,
            True,
        )
        return result

    def try_process_first_step(self) -> Result:
        if self.app_state.first_step != Keys.NONE or not self.input_key.is_first_step:
            return None
        result = self.create_result(
            self.app_state.state,
            self.input_key.key,
            self.app_state.prevent_esc_on_caps_up,
            self.app_state.modificators,
            [],
            self.input_key.is_letter_or_digit,
        )
        return result

    def process_normal_and_insert_with_capital(self) -> Result:
        if self.app_state.state == OFF or not self.app_state.modificators.caps:
            return None
        send = self.config.try_get_caps_send(self.input_key.key)
        if not send:
            return None
        result = self.create_result(
            self.app_state.state,
            Keys.NONE,
            True,
            self.app_state.modificators,
            send,
            True,
        )
        return result

    def create_result(
        self,
        state,
        first_step: Keys,
        prevent_esc_on_caps_up,
        modificators,
        send: List[Keys],
        prevent_key_process,
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
        return result

    def create_result_with_app_state(
        self, app_state, send: List[Keys], prevent_key_process
    ) -> Result:
        result = Result()
        result.app_state = app_state
        result.send = send
        result.prevent_key_process = prevent_key_process
        return result

    def get_next_modificators(self) -> Modificators:
        down = not self.is_key_up
        control = self.app_state.modificators.control
        shift = self.app_state.modificators.shift
        alt = self.app_state.modificators.alt
        win = self.app_state.modificators.win
        caps = self.app_state.modificators.caps
        if self.input_key.is_control:
            control = down
        if self.input_key.is_shift:
            shift = down
        if self.input_key.is_alt:
            alt = down
        if self.input_key.is_win:
            win = down
        if self.input_key.is_caps:
            caps = down

        modificators = Modificators()
        modificators.control = control
        modificators.shift = shift
        modificators.alt = alt
        modificators.win = win
        modificators.caps = caps

        return modificators

    def try_process_command_key(self):
        if not self.app_state.modificators.caps:
            return None
        if self.input_key.key == Keys.BACKSPACE:  # TODO command to config
            return self.create_result_with_app_state(
                self.app_state, [Keys.COMMAND_EXIT], True
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
