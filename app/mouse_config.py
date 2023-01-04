import logging
from collections import defaultdict
from pathlib import Path
from typing import Union

import yaml

logger = logging.getLogger(__name__)


class MouseConfig:
    def __init__(self):
        self.positions = defaultdict(list)

    @classmethod
    def from_file(cls, path: Union[str, Path] = "mouse_config.yaml"):
        mouse_config = cls()
        with open(path, "r") as f:
            config_data: dict = yaml.safe_load(f)

        mouse_config.positions = config_data
        return mouse_config
