import os
from typing import Dict, List, Any, Union
import yaml
from pathlib import Path

from app.enums import Keys, string_to_multi_keys


class Config:
    def __init__(self):

        self.caps = {}
        self.common = {}
        self.two_steps = {}
        self.two_steps_commands = {}

    @classmethod
    def from_file(cls, path: Union[str, Path] = "config.yaml"):
        config = cls()
        with open(path, "r") as f:
            config_data: dict = yaml.safe_load(f)
        config.caps = config.convert_dict(config_data.pop("caps"))
        config.common = config.convert_dict(config_data.pop("common"))
        dct = {}
        for ts in config_data:
            dct[Keys.from_string(ts)] = config.convert_dict(config_data[ts])
        config.two_steps = dct
        dct = {}
        for ts in config_data:
            dct[Keys.from_string(ts)] = config.convert_dict_commands(config_data[ts])
        config.two_steps_commands = dct
        config.try_load_users_config(path)
        return config

    def try_load_users_config(self, path):
        user_config = Path(path).parent / "user_config.yaml"
        if not os.path.exists(user_config):
            return
        with open(user_config, "r") as f:
            config_data: dict = yaml.safe_load(f)
        dct = {}
        for ts in config_data:
            dct[Keys.from_string(ts)] = self.convert_dict_commands(config_data[ts])
        # TODO: fix override
        self.two_steps_commands.update(dct)


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
        print(f"MISSING TWO STEP KEY for {firstStep} and {key}")
        return []

    def try_get_two_key_command(self, firstStep: Keys, key: Keys) -> str:
        keys_two_step: dict = self.two_steps_commands.get(firstStep, {})
        cmd = keys_two_step.get(key)
        if cmd:
            return cmd
        print(f"MISSING TWO STEP KEY for {firstStep} and {key}")
        return ""


    def try_get_caps_send(self, key: Keys) -> List[Keys]:
        return self.caps.get(key, [])

    @staticmethod
    def convert_dict_commands(d: Dict[str, str]) -> Dict[Keys, str]:
        result = {}

        # TODO: fix that
        def parse_command(str) -> str:
            str = str.replace("__command__", "").lstrip("<").rstrip(">")
            if "C:" in str:
                str = fr'{str}'
            return str

        for key in d:
            cmd = d[key]
            if not "__command__" in cmd:
                continue
            result[Keys.from_string(key)] = parse_command(d[key])
        return result

