import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union, Optional

import yaml

from app.events import SendEvent, CMDEvent, WriteEvent, Event, EventLike
from app.keys import Keys, string_to_multi_keys

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        self.special_key = Keys.NONE
        self.change_mode_key = Keys.NONE
        self.off_mode_key = Keys.NONE
        self.mouse_mode_key = Keys.NONE
        self.exit_key = Keys.NONE
        self.help_key = Keys.NONE
        self.diagnostic_key = Keys.NONE
        self.special = {}
        self.common = {}
        self.two_step_events = defaultdict(dict)

    @classmethod
    def from_file(cls, path: Union[str, Path] = "config.yaml"):
        config = cls()
        with open(path, "r") as f:
            config_data: dict = yaml.safe_load(f)

        config.special_key = Keys.from_string(config_data.pop("special_key"))
        config.change_mode_key = Keys.from_string(config_data.pop("change_mode_key"))
        config.off_mode_key = Keys.from_string(config_data.pop("off_mode_key"))
        config.mouse_mode_key = Keys.from_string(config_data.pop("mouse_mode_key"))
        config.exit_key = Keys.from_string(config_data.pop("exit_key"))
        config.help_key = Keys.from_string(config_data.pop("help_key"))
        config.diagnostic_key = Keys.from_string(config_data.pop("diagnostic_key"))

        config.special = config.convert_dict(config_data.pop("special"))
        config.common = config.convert_dict(config_data.pop("common"))

        dct = {}
        for fs in config_data:
            events = config._convert_dict_events(config_data[fs])
            dct[Keys.from_string(fs)] = events
        config.two_step_events = dct

        config.try_load_users_config()
        return config

    def try_load_users_config(self):
        user_config = Path(os.getenv("HOMEPATH")) / ".dokey" / "user_config.yaml"
        if not os.path.exists(user_config):
            return
        with open(user_config, "r") as f:
            config_data: dict = yaml.safe_load(f)
        for fs in config_data:
            events = self._convert_dict_events(config_data[fs])
            first_step = Keys.from_string(fs)
            # if first_step not in self.two_step_events:
            #     self.two_step_events[first_step] = {}
            section = self.two_step_events.get(first_step)
            section.update(events)

    @staticmethod
    def convert_dict(d: Dict[str, str]) -> Dict[Keys, Keys]:
        result = {}
        for key in d:
            result[Keys.from_string(key)] = string_to_multi_keys(d[key])
        return result

    def try_get_two_key_send(self, firstStep: Keys, key: Keys) -> List[Keys]:
        keys_two_step: dict = self.two_steps.get(firstStep, {})
        keys = keys_two_step.get(key)
        if keys:
            return keys
        logger.warning(f"MISSING TWO STEP KEY for {firstStep} and {key}")
        return []

    def try_get_two_key_command(self, firstStep: Keys, key: Keys) -> str:
        keys_two_step: dict = self.two_steps_commands.get(firstStep, {})
        cmd = keys_two_step.get(key)
        if cmd:
            return cmd
        logger.warning(f"MISSING TWO STEP KEY for {firstStep} and {key}")
        return ""

    def try_get_special_send(self, key: Keys) -> EventLike:
        send = self.special.get(key, [])
        if not send:
            return Event(True)
        return SendEvent(send=send)

    @staticmethod
    def _parse_config_value_to_event(val: str) -> EventLike:
        if val.startswith("__command__"):
            cmd = val.replace("__command__", "").lstrip("<").rstrip(">")
            if "C:" in cmd:  # TODO: fix that
                cmd = rf"{cmd}"
            return CMDEvent(cmd=cmd)
        if val.startswith("__write__"):
            text = val.replace("__write__", "").lstrip("<").rstrip(">")
            return WriteEvent(text=text)
        send = string_to_multi_keys(val)
        return SendEvent(send=send)

    @staticmethod
    def _convert_dict_events(d: Dict[str, str]) -> Dict[Keys, EventLike]:
        result = {}
        for key in d:
            result[Keys.from_string(key)] = Config._parse_config_value_to_event(d[key])
        return result

    def get_single_step_send_event(self, key: Keys) -> Optional[SendEvent]:
        send = self.common.get(key)
        if not send:
            return None
        return SendEvent(send)

    def get_two_step_event(self, first_step: Keys, key: Keys) -> Optional[EventLike]:

        keys_two_step: dict = self.two_step_events.get(first_step, {})
        event = keys_two_step.get(key)
        if not event:
            logger.warning(f"MISSING TWO STEP KEY for {first_step} and {key}")
            return None
        return event
