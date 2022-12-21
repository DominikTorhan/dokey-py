from typing import List, Optional
from app.current_state import CurrentState, OFF, NORMAL, INSERT
from app.config import Config
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


class Result:
    def __init__(self):
        self.mode = -1
        self.first_step = Keys.NONE
        self.app_state: CurrentState = None
        self.send: List[Keys] = []
        self.cmd = ""
        self.prevent_key_process: bool = False
        self.modificators = None
        self.prevent_esc_on_caps_up = False


class KeyProcessor:
    def __init__(self, config):
        self.config: Config = config
        self.app_state: CurrentState = None

    def process(
        self,
        key: Keys,
        is_key_up=False,
        mode: int = NORMAL,
        modifs_os: Modificators = None,
        first_step=Keys.NONE,
        prevent_esc_on_caps_up=False,
    ) -> Result:
        # process CAPSLOCK
        if key.is_caps():
            return self.process_capital(key, is_key_up, mode, prevent_esc_on_caps_up)
        # process Modificators
        if key.is_modif_ex():
            return self.process_modificators(
                key, is_key_up, mode, first_step, prevent_esc_on_caps_up
            )

        # try update modifiers by OS modifiers. only when non modifier is pressed.
        self.try_update_modifiers_by_os(modifs_os)

        if is_key_up:
            return self.create_result_with_app_state(
                app_state=self.app_state,
                mode=mode,
                first_step=first_step,
                prevent_esc_on_caps_up=prevent_esc_on_caps_up,
            )

        # mode Change
        new_mode, new_prevent_esc_on_caps_up = self.try_process_mode_change(
            key, mode, prevent_esc_on_caps_up
        )
        if new_mode > -1:
            app_state = CurrentState()
            app_state.modificators = self.app_state.modificators
            result = self.create_result_with_app_state(
                app_state,
                True,
                first_step=first_step,
                prevent_esc_on_caps_up=prevent_esc_on_caps_up,
            )
            result.mode = new_mode
            result.prevent_esc_on_caps_up = new_prevent_esc_on_caps_up
            result.modificators = self.app_state.modificators
            return result

        # single step
        result = self.try_process_single_step(
            key, mode, first_step, prevent_esc_on_caps_up
        )
        if result is not None:
            return result

        # two-step
        result = self.try_process_two_step(
            key, mode, first_step, prevent_esc_on_caps_up
        )
        if result is not None:
            return result

        # command key
        result = self.try_process_command_key(
            key, first_step=first_step, prevent_esc_on_caps_up=prevent_esc_on_caps_up
        )
        if result is not None:
            return result

        # caps key
        result = self.process_normal_and_insert_with_capital(key, mode)
        return result

    def try_process_mode_change(
        self, key: Keys, mode: int, prevent_esc_on_caps_up
    ) -> (Optional[int], bool):
        if self.app_state.modificators.caps:
            # TODO mode keys in config?
            mode_off_key = Keys.Q
            mode_change_key = Keys.F
            if key == mode_off_key:
                return OFF, True

            if key == mode_change_key:
                return get_next_mode(mode), True

            return -1, False

        if key.is_esc() and mode == INSERT:
            return get_prev_mode(mode), prevent_esc_on_caps_up

        return -1, False

    def process_capital(
        self, key: Keys, is_key_up: bool, mode: int, prevent_esc_on_caps_up
    ) -> Result:
        new_prevent_esc_on_caps_up = prevent_esc_on_caps_up
        new_mode = mode
        if is_key_up and not new_prevent_esc_on_caps_up and mode == INSERT:
            new_mode = NORMAL  # prev mode at esc
        if is_key_up and new_prevent_esc_on_caps_up:
            new_prevent_esc_on_caps_up = False
        modificators = self.get_next_modificators(key, is_key_up)  # only for CAPS?!
        result = self.create_result(
            new_mode, Keys.NONE, new_prevent_esc_on_caps_up, modificators, True
        )
        return result

    def process_modificators(
        self, key: Keys, is_key_up: bool, mode: int, first_step, prevent_esc_on_caps_up
    ) -> Result:
        modificators = self.get_next_modificators(key, is_key_up)
        result = self.create_result(
            mode,  # TODO: is not needed here
            first_step,
            prevent_esc_on_caps_up,
            modificators,
        )
        return result

    def try_process_single_step(
        self, key: Keys, mode: int, first_step, prevent_esc_on_caps_up
    ) -> Optional[Result]:
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None
        if mode != NORMAL:
            return None
        if first_step != Keys.NONE:
            return None
        result = self.try_process_first_step(
            key, mode, first_step, prevent_esc_on_caps_up
        )
        if result:
            return result
        if key.is_first_step():
            return None

        send = self.config.common.get(key)
        if not send:
            return None
        return self.create_result_with_app_state(
            self.app_state,
            True,
            send,
            mode=mode,
            first_step=first_step,
            prevent_esc_on_caps_up=prevent_esc_on_caps_up,
        )

    def try_process_two_step(
        self, key: Keys, mode: int, first_step, prevent_esc_on_caps_up
    ) -> Optional[Result]:
        if mode != NORMAL:
            return None
        if self.app_state.modificators.caps or self.app_state.modificators.win:
            return None

        if first_step == Keys.NONE:
            return None

        send = self.config.try_get_two_key_send(first_step, key)
        cmd = ""
        if not send or send == [None]:
            cmd = self.config.try_get_two_key_command(first_step, key)
        result = self.create_result(
            mode,
            Keys.NONE,
            prevent_esc_on_caps_up,
            self.app_state.modificators,
            True,
            send,
            cmd=cmd,
        )
        return result

    def try_process_first_step(
        self, key: Keys, mode: int, first_step: Keys, prevent_esc_on_caps_up
    ) -> Optional[Result]:
        if first_step != Keys.NONE or not key.is_first_step():
            return None
        result = self.create_result(
            mode,  # TODO: not needed here
            key,
            prevent_esc_on_caps_up,
            self.app_state.modificators,
            key.is_letter_or_digit(),
        )
        return result

    def process_normal_and_insert_with_capital(
        self, key: Keys, mode: int
    ) -> Optional[Result]:
        if mode == OFF or not self.app_state.modificators.caps:
            return None
        send = self.config.try_get_caps_send(key)
        if not send:
            return None
        result = self.create_result(
            mode,
            Keys.NONE,
            True,
            self.app_state.modificators,
            True,
            send,
        )
        return result

    def create_result(
        self,
        mode: int,
        first_step: Keys,
        prevent_esc_on_caps_up,
        modificators,
        prevent_key_process=False,
        send: List[Keys] = [],
        cmd: str = "",
    ) -> Result:
        result = Result()
        result.first_step = first_step
        result.mode = mode
        result.modificators = modificators
        result.prevent_esc_on_caps_up = prevent_esc_on_caps_up
        result.send = send
        result.prevent_key_process = prevent_key_process
        result.cmd = cmd
        return result

    def create_result_with_app_state(
        self,
        app_state,
        prevent_key_process=False,
        send: List[Keys] = [],
        mode=-1,
        first_step=Keys.NONE,
        prevent_esc_on_caps_up=False,
    ) -> Result:
        result = Result()
        result.first_step = first_step
        result.mode = mode
        result.app_state = app_state
        result.modificators = app_state.modificators
        result.prevent_esc_on_caps_up = prevent_esc_on_caps_up
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

    def try_process_command_key(
        self, key: Keys, first_step: Keys, prevent_esc_on_caps_up
    ):
        if not self.app_state.modificators.caps:
            return None
        if key == Keys.BACKSPACE:  # TODO command to config
            return self.create_result_with_app_state(
                self.app_state,
                True,
                [Keys.COMMAND_EXIT],
                first_step=first_step,
                prevent_esc_on_caps_up=prevent_esc_on_caps_up,
            )

    def try_update_modifiers_by_os(self, modifs_os: Modificators):
        """
        Solution of windows lock win+l. Win is down. We can't receive up event! Modifs_os is additional
        state of modifires.
        """
        if not modifs_os:
            return

        if not modifs_os.win and self.app_state.modificators.win:
            self.app_state.modificators.win = False  # for windows lock win+l issue
        if not modifs_os.control and self.app_state.modificators.control:
            self.app_state.modificators.control = False
        if not modifs_os.shift and self.app_state.modificators.shift:
            self.app_state.modificators.shift = False
        if not modifs_os.alt and self.app_state.modificators.alt:
            self.app_state.modificators.alt = False
