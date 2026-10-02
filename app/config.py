import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Union, Optional

from app import yaml_lite

from app.events import (
    SendEvent,
    CMDEvent,
    FocusWindowEvent,
    FocusOrLaunchEvent,
    WriteEvent,
    Event,
    EventLike,
)
from app.keys import FIRST_STEPS, VALUE_MARKERS, Keys, string_to_multi_keys

logger = logging.getLogger(__name__)


def dokey_dir() -> Path:
    """Directory holding the user's overrides (~/.dokey).

    Path.home() rather than HOMEPATH. On Windows HOMEPATH is drive-relative
    ("\\Users\\dto"), so reading it directly resolves against whatever drive
    happens to be current - launch DoKey from D: and it would silently load a
    different user_config.yaml, one that can run commands. Path.home() already
    consults USERPROFILE and falls back to HOMEDRIVE + HOMEPATH, which is the
    redirect-aware lookup we wanted, with the drive attached.
    """
    return Path.home() / ".dokey"


class Config:
    def __init__(self):
        self.special_key = Keys.NONE
        self.change_mode_key = Keys.NONE
        self.off_mode_key = Keys.NONE
        self.mouse_mode_key = Keys.NONE
        self.exit_key = Keys.NONE
        self.clear_screen_key = Keys.NONE
        self.help_key = Keys.NONE
        self.diagnostic_key = Keys.NONE
        self.keyboard_key = Keys.NONE
        self.special = {}
        self.common = {}
        self.two_step_events = defaultdict(dict)
        # Which keys open a two-step chord. In v1 this is the hand-maintained
        # FIRST_STEPS list, because there a section is dead unless the key is
        # also listed there. In v2 it is simply the sections that exist, which
        # is what removes the "two edits for one binding" trap.
        self.first_steps = set(FIRST_STEPS)
        # Optional human names for layers and chord sections, shown by the
        # keyboard overlay. Presentation only; nothing dispatches on them.
        self.titles = {}

    def is_first_step(self, key: Keys) -> bool:
        return key in self.first_steps

    # Names of the control keys, in the order KeyProcessor.process() reaches
    # them. Shared by the loader and the keyboard overlay so the picture cannot
    # disagree with the code about which control wins a shared key.
    CONTROL_KEYS = (
        ("help", "help_key"),
        ("diagnostic", "diagnostic_key"),
        ("keyboard", "keyboard_key"),
        ("off_mode", "off_mode_key"),
        ("change_mode", "change_mode_key"),
        ("mouse_mode", "mouse_mode_key"),
        ("exit", "exit_key"),
        ("clear_screen", "clear_screen_key"),
    )

    LAYERS = ("special", "common")

    @classmethod
    def from_file(cls, path: Union[str, Path] = "config.yaml"):
        config = cls()
        with open(path, "r") as f:
            config_data: dict = yaml_lite.safe_load(f)

        # "version" is absent from every file written before the restructure,
        # and in v1 an unrecognised top-level key silently becomes a first step
        # - so it has to come off the dict before anything else looks at it.
        version = config_data.pop("version", 1)
        if version == 2:
            config._load_v2(config_data)
        elif version == 1:
            config._load_v1(config_data)
        else:
            raise ValueError(f"unsupported config version {version!r}")

        config.try_load_users_config()
        return config

    def _load_v1(self, data: dict):
        """The original flat layout: control keys, two known sections, and
        "every other top-level key is a first step"."""
        self.special_key = Keys.from_string(data.pop("special_key"))
        for name, attribute in self.CONTROL_KEYS:
            # keyboard_key is defaulted rather than required: a config written
            # before the overlay existed must still load, and an unpopped key
            # would be read as a two-step first step called "keyboard_key".
            if attribute == "keyboard_key":
                raw = data.pop("keyboard_key", "apostrophe")
            else:
                raw = data.pop(attribute)
            setattr(self, attribute, Keys.from_string(raw))

        self.special = self.convert_dict(data.pop("special"))
        self.common = self.convert_dict(data.pop("common"))

        # v1 keeps the hand-maintained list: a section whose key is missing
        # from FIRST_STEPS does nothing, and pretending otherwise here would
        # change behaviour on files that already rely on it.
        self.first_steps = set(FIRST_STEPS)
        self.two_step_events = {
            Keys.from_string(name): self._convert_dict_events(section)
            for name, section in data.items()
        }

    def _load_v2(self, data: dict):
        """The self-describing layout: keys, layers and two_step are named, so
        an unknown top-level key is an error instead of an accidental chord."""
        keys = data.pop("keys", None)
        if not isinstance(keys, dict):
            raise ValueError("config version 2 needs a 'keys:' mapping")
        self.special_key = Keys.from_string(keys.pop("special"))
        for name, attribute in self.CONTROL_KEYS:
            if name in keys:
                setattr(self, attribute, Keys.from_string(keys.pop(name)))
        if keys:
            raise ValueError(f"unknown entries under keys: {sorted(keys)}")

        for name, section in (data.pop("layers", None) or {}).items():
            if name not in self.LAYERS:
                raise ValueError(f"unknown layer {name!r}, expected {self.LAYERS}")
            setattr(self, name, self.convert_dict(self._bindings(section)))
            self._remember_title(name, section)

        two_step = data.pop("two_step", None) or {}
        self.two_step_events = {}
        for name, section in two_step.items():
            key = Keys.from_string(name)
            if key is None:
                raise ValueError(f"two_step section {name!r} is not a key name")
            self.two_step_events[key] = self._convert_dict_events(
                self._bindings(section)
            )
            self._remember_title(f"two_step.{name}", section)
        # the sections that exist are the first steps; no second list to keep
        # in step with this one
        self.first_steps = set(self.two_step_events)

        if data:
            raise ValueError(f"unknown top-level keys: {sorted(data)}")

    @staticmethod
    def _bindings(section) -> dict:
        """A section is {title?, bindings?}; a missing bindings block is empty.

        An empty section is meaningful rather than pointless: it keeps a key
        registered as a first step, so it still swallows the next keystroke.
        """
        if section is None:
            return {}
        if not isinstance(section, dict):
            raise ValueError(f"section must be a mapping, got {type(section).__name__}")
        return section.get("bindings") or {}

    def _remember_title(self, name, section):
        if isinstance(section, dict) and section.get("title"):
            self.titles[name] = str(section["title"])

    def try_load_users_config(self):
        """Merge ~/.dokey/user_config.yaml over the shipped keymap.

        Failures here never stop DoKey: this is the file the owner hand-edits,
        it lives outside the repo, and a stray character in it used to raise
        straight out of from_file and prevent the app starting at all. The
        error's own text is deliberately not logged - a parse error quotes the
        offending line, and these files hold addresses and logins.
        """
        user_config = dokey_dir() / "user_config.yaml"
        if not os.path.exists(user_config):
            return
        try:
            with open(user_config, "r") as f:
                data = yaml_lite.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError("top level is not a mapping")
            merged = self._merge_user_config(data)
        except (OSError, ValueError) as error:
            logger.error(
                "Ignoring %s (%s); keeping the shipped keymap",
                user_config,
                type(error).__name__,
            )
            return
        logger.info("Merged %s overrides from %s", merged, user_config)

    def _merge_user_config(self, data: dict) -> int:
        """Apply the overrides, returning how many bindings were merged.

        A v1 file is two-step sections and nothing else. A v2 file may also
        override control keys and layers, which v1 silently could not: a
        "special:" block there parsed as a first step named "special", became a
        None key, and did nothing.
        """
        version = data.pop("version", 1)
        if version not in (1, 2):
            raise ValueError(f"unsupported user config version {version!r}")

        if version == 1:
            sections = {name: {"bindings": body} for name, body in data.items()}
            keys, layers = {}, {}
        else:
            keys = data.pop("keys", None) or {}
            layers = data.pop("layers", None) or {}
            sections = data.pop("two_step", None) or {}
            if data:
                raise ValueError(f"unknown top-level keys: {sorted(data)}")

        merged = 0
        for name, raw in keys.items():
            if name == "special":
                self.special_key = Keys.from_string(raw)
                merged += 1
                continue
            attribute = dict(self.CONTROL_KEYS).get(name)
            if attribute is None:
                raise ValueError(f"unknown control key {name!r}")
            setattr(self, attribute, Keys.from_string(raw))
            merged += 1

        for name, section in layers.items():
            if name not in self.LAYERS:
                raise ValueError(f"unknown layer {name!r}, expected {self.LAYERS}")
            bindings = self.convert_dict(self._bindings(section))
            getattr(self, name).update(bindings)
            merged += len(bindings)

        for name, section in sections.items():
            first_step = Keys.from_string(name)
            events = self._convert_dict_events(self._bindings(section))
            existing = self.two_step_events.setdefault(first_step, {})
            existing.update(events)
            merged += len(events)
            if first_step is not None:
                # a section the user introduces is a first step, whichever
                # format they wrote it in; without this it parsed fine and then
                # never fired, which is the oldest trap in this config
                self.first_steps.add(first_step)
            self._remember_title(f"two_step.{name}", section)
        return merged

    @staticmethod
    def convert_dict(d: Dict[str, str]) -> Dict[Keys, Keys]:
        """Layers hold key sends only.

        A __write__ or __command__ entry here would otherwise be split into
        "key names" and reported one failed lookup at a time, with the value in
        every message. Refuse it up front, and name only the marker.
        """
        result = {}
        for key, value in d.items():
            marker = next(
                (m for m in VALUE_MARKERS if str(value).startswith(m)), None
            )
            if marker:
                raise ValueError(
                    f"{marker} is not supported in a layer (key {key!r}); "
                    "put it in a two_step section"
                )
            result[Keys.from_string(key)] = string_to_multi_keys(value)
        return result

    def try_get_special_send(self, key: Keys) -> EventLike:
        send = self.special.get(key, [])
        if not send:
            return Event(True)
        return SendEvent(send=send)

    @staticmethod
    def _parse_config_value_to_event(val: str) -> Optional[EventLike]:
        if val.startswith("__command__"):
            cmd = val.replace("__command__", "").lstrip("<").rstrip(">")
            return CMDEvent(cmd=cmd)
        if val.startswith("__focus__"):
            return Config._parse_focus(val)
        if val.startswith("__focus_or_launch__"):
            return Config._parse_focus_or_launch(val)
        if val.startswith("__write__"):
            text = val.replace("__write__", "").lstrip("<").rstrip(">")
            return WriteEvent(text=text)
        send = string_to_multi_keys(val)
        return SendEvent(send=send)

    @staticmethod
    def _parse_focus(val: str) -> Optional[FocusWindowEvent]:
        # a bad target is logged and the binding dropped: a typo in
        # user_config.yaml must not stop DoKey from starting
        target = val[len("__focus__") :].lstrip("<").rstrip(">")
        process, separator, title_prefix = target.partition("::")
        process = process.strip()
        title_prefix = title_prefix.strip()
        if not separator or not process or not title_prefix:
            logger.error(
                "Invalid %r: __focus__ requires <process.exe::title prefix>", val
            )
            return None
        return FocusWindowEvent(process, title_prefix)

    @staticmethod
    def _parse_focus_or_launch(val: str) -> Optional[FocusOrLaunchEvent]:
        target = val[len("__focus_or_launch__") :].lstrip("<").rstrip(">")
        process, separator, remainder = target.partition("::")
        app_id, command_separator, cmd = remainder.partition("::")
        process = process.strip()
        app_id = app_id.strip()
        cmd = cmd.strip()
        if (
            not separator
            or not command_separator
            or not process
            or not app_id
            or not cmd
        ):
            logger.error(
                "Invalid %r: __focus_or_launch__ requires "
                "<process.exe::AppUserModelID::command>",
                val,
            )
            return None
        return FocusOrLaunchEvent(process, app_id, cmd)

    @staticmethod
    def _convert_dict_events(d: Dict[str, str]) -> Dict[Keys, EventLike]:
        result = {}
        for key in d:
            event = Config._parse_config_value_to_event(d[key])
            if event is not None:
                result[Keys.from_string(key)] = event
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
            return None
        return event
