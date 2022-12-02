from typing import Dict
import yaml

from app.enums import Keys, string_to_multi_keys


class Config:
    def __init__(self):

        self.caps = {}
        self.common = {}
        self.two_steps = {}

    @classmethod
    def from_file(cls, path: str = "config.yaml"):
        config = cls()
        with open(path, "r") as f:
            config_data: dict = yaml.safe_load(f)
        config.caps = config.convert_dict(config_data.pop("caps"))
        config.common = config.convert_dict(config_data.pop("common"))
        dct = {}
        for ts in config_data:
            dct[Keys.from_string(ts)] = config.convert_dict(config_data[ts])
        config.two_steps = dct
        return config

    @staticmethod
    def convert_dict(d: Dict[str,str]) -> Dict[Keys,Keys]:
        result = {}
        for key in d:
            result[Keys.from_string(key)] = string_to_multi_keys(d[key])
        return result

    def try_get_two_key_send(self, firstStep: Keys, key: Keys) -> str:
        keys: dict = self.two_steps.get(firstStep, {})
        return keys.get(key, "")

    def try_get_caps_send(self, key: Keys) -> str:
        return self.caps.get(key, "")
