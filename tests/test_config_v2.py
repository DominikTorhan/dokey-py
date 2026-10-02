import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.events import SendEvent, WriteEvent  # noqa: F401


def shape(events):
    """Two-step sections hold event objects, which do not compare by value."""
    return {
        key.name: (type(event).__name__, getattr(event, "send", None))
        for key, event in events.items()
    }
from app.keys import Keys

V1 = """
special_key: capital
change_mode_key: f
off_mode_key: q
mouse_mode_key: u
clear_screen_key: s
exit_key: esc
help_key: slash
diagnostic_key: backslash
keyboard_key: apostrophe

special:
  h: backspace

common:
  j: down

i:
  j: end, enter
  d1: __command__<notepad>
"""

V2 = """
version: 2
keys:
  special: capital
  change_mode: f
  off_mode: q
  mouse_mode: u
  clear_screen: s
  exit: esc
  help: slash
  diagnostic: backslash
  keyboard: apostrophe

layers:
  special:
    bindings:
      h: backspace
  common:
    title: Normal mode
    bindings:
      j: down

two_step:
  i:
    title: Insert helpers
    bindings:
      j: end, enter
      d1: __command__<notepad>
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.home = Path(tempfile.mkdtemp())

    def write(self, text, name="config.yaml"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def load(self, text):
        with patch("app.config.dokey_dir", return_value=self.home):
            return Config.from_file(self.write(text))

    def user(self, base, override):
        (self.home / "user_config.yaml").write_text(override, encoding="utf-8")
        with patch("app.config.dokey_dir", return_value=self.home):
            return Config.from_file(self.write(base))


class TestVersion2(Base):
    def test_v1_and_v2_describe_the_same_keymap(self):
        # the whole point: converting a live config must change nothing
        one, two = self.load(V1), self.load(V2)
        for _, attribute in Config.CONTROL_KEYS:
            self.assertEqual(getattr(one, attribute), getattr(two, attribute))
        self.assertEqual(one.special_key, two.special_key)
        self.assertEqual(one.special, two.special)
        self.assertEqual(one.common, two.common)
        self.assertEqual(
            {k.name: shape(v) for k, v in one.two_step_events.items() if v},
            {k.name: shape(v) for k, v in two.two_step_events.items() if v},
        )

    def test_first_steps_come_from_the_sections_that_exist(self):
        # v1 needs FIRST_STEPS kept in step by hand; v2 derives it
        self.assertEqual({Keys.I}, self.load(V2).first_steps)

    def test_a_section_with_no_bindings_is_still_a_first_step(self):
        # it swallows the next keystroke, so dropping it would change behaviour
        config = self.load(V2 + "\n  s:\n    title: unused\n")
        self.assertIn(Keys.S, config.first_steps)
        self.assertEqual({}, config.two_step_events[Keys.S])

    def test_titles_are_captured_for_the_overlay(self):
        config = self.load(V2)
        self.assertEqual("Insert helpers", config.titles["two_step.i"])
        self.assertEqual("Normal mode", config.titles["common"])

    def test_an_unknown_top_level_key_is_an_error_not_a_chord(self):
        # in v1 this typo silently became a first step nobody could press
        with self.assertRaises(ValueError) as caught:
            self.load(V2 + "\ntwo_stepp:\n  x:\n")
        self.assertIn("two_stepp", str(caught.exception))

    def test_unknown_layer_and_control_names_are_refused(self):
        with self.assertRaises(ValueError):
            self.load(V2.replace("  common:\n    title", "  commonn:\n    title"))
        with self.assertRaises(ValueError):
            self.load(V2.replace("  help: slash", "  helpp: slash"))

    def test_an_unsupported_version_is_refused(self):
        with self.assertRaises(ValueError):
            self.load(V2.replace("version: 2", "version: 7"))


class TestUserOverrides(Base):
    def test_an_old_user_config_still_merges_over_a_v2_base(self):
        config = self.user(V2, "i:\n  j: home\nq:\n  a: __write__<hi>\n")
        self.assertEqual([Keys.HOME], config.two_step_events[Keys.I][Keys.J].send)
        self.assertIsInstance(config.two_step_events[Keys.Q][Keys.A], WriteEvent)

    def test_a_user_section_becomes_a_first_step(self):
        # it parsed fine and then never fired; the oldest trap in this config
        config = self.user(V2, "q:\n  a: __write__<hi>\n")
        self.assertIn(Keys.Q, config.first_steps)

    def test_a_v2_user_config_can_override_layers_and_control_keys(self):
        # none of this was reachable from the old format
        config = self.user(
            V2,
            "version: 2\n"
            "keys:\n  keyboard: semicolon\n"
            "layers:\n  common:\n    bindings:\n      g: ctrl+home\n",
        )
        self.assertEqual(Keys.SEMICOLON, config.keyboard_key)
        self.assertIn(Keys.G, config.common)
        self.assertEqual([Keys.DOWN], config.common[Keys.J], "base binding kept")

    def test_a_broken_user_config_does_not_stop_dokey_starting(self):
        with self.assertLogs("app.config", level="ERROR"):
            config = self.user(V2, "i:\n  - not a mapping\n   bad indent\n")
        self.assertEqual(
            [Keys.END, Keys.ENTER], config.two_step_events[Keys.I][Keys.J].send
        )

    def test_the_failure_log_does_not_quote_the_file(self):
        # parse errors name the offending line, and these files hold addresses,
        # logins and private URLs
        secret = "__write__<super-secret-passphrase>"
        with self.assertLogs("app.config", level="ERROR") as caught:
            self.user(V2, f"i:\n  d1: {secret}\n   bad indent\n")
        self.assertNotIn("secret", "\n".join(caught.output))


if __name__ == "__main__":
    unittest.main()
