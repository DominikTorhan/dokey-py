import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Config
from app.events import CMDEvent, SendEvent, WriteEvent
from app.keys import FIRST_STEPS, Keys

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "app" / "config.yaml"
EXAMPLE_PATH = REPO_ROOT / "app" / "user_config.example.yaml"


class TestUserConfigExample(unittest.TestCase):
    """The example is documentation, and documentation rots quietly.

    It is the only description of the user-override format that ships with
    DoKey, so it is worth proving that it still loads through the real code
    path rather than trusting that it reads plausibly.
    """

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        shutil.copy(EXAMPLE_PATH, self.directory / "user_config.yaml")

    def load(self):
        with patch("app.config.dokey_dir", return_value=self.directory):
            return Config.from_file(CONFIG_PATH)

    def test_it_loads_as_a_real_user_config(self):
        config = self.load()
        # nothing landed under the None key, which is where an unusable
        # top-level name ends up
        self.assertNotIn(None, config.two_step_events)

    def test_every_section_is_a_usable_first_step(self):
        # a section whose name is not in FIRST_STEPS is silently dead, so an
        # example containing one would be teaching the wrong thing
        plain = Config.from_file(CONFIG_PATH)
        with patch.object(Config, "try_load_users_config"):
            base = set(Config.from_file(CONFIG_PATH).two_step_events)
        for first_step in set(self.load().two_step_events) - base:
            self.assertIn(first_step, FIRST_STEPS)
        self.assertIsNotNone(plain)

    def test_every_example_binding_produces_a_real_event(self):
        config = self.load()
        seen = 0
        for entries in config.two_step_events.values():
            for key, event in entries.items():
                self.assertIsNotNone(key, "unknown key name in the example")
                self.assertIsInstance(event, (SendEvent, CMDEvent, WriteEvent))
                if isinstance(event, SendEvent):
                    self.assertNotIn(None, event.send)
                seen += 1
        self.assertGreater(seen, 0)

    def test_it_actually_overrides_the_shipped_keymap(self):
        # an example that changes nothing would not demonstrate anything
        with patch.object(Config, "try_load_users_config"):
            base = Config.from_file(CONFIG_PATH)
        merged = self.load()
        overridden = [
            (first_step, key)
            for first_step, entries in merged.two_step_events.items()
            for key, event in entries.items()
            if base.two_step_events.get(first_step, {}).get(key) is not event
        ]
        self.assertTrue(overridden, "the example overrides nothing")

    def test_the_example_carries_no_live_credentials_shaped_text(self):
        # it is committed, unlike the real one; keep it obviously fake
        text = EXAMPLE_PATH.read_text(encoding="utf-8")
        for marker in ("@gmail.", "@protonmail.", "@o2.", "@nvidia."):
            self.assertNotIn(marker, text, f"{marker} looks like a real address")


if __name__ == "__main__":
    unittest.main()
