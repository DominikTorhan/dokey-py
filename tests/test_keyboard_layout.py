import unittest
from pathlib import Path

from app.config import Config
from app.keyboard_layout import (
    ROW_WIDTH,
    ROWS,
    TABS,
    build,
    describe,
    unplaced_controls,
)
from app.keys import Keys, string_to_multi_keys

CONFIG_PATH = Path(__file__).parent.parent / "app" / "config.yaml"

# The whole point of the overlay is the alphanumeric block. If any of these ever
# turn up as a cap, the picture has grown the clutter it was meant to leave out.
EXCLUDED = [
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "left", "right", "up", "down",
    "home", "end", "page up", "page down",
    "ins", "del", "print screen",
]


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.config = Config.from_file(CONFIG_PATH)
        self.rows = build(self.config)

    def caps(self, tab=TABS[0]):
        return {cap.key: cap for row in build(self.config, tab) for cap in row}

    def test_every_row_is_a_full_keyboard_width(self):
        # a row that does not sum to ROW_WIDTH draws as a ragged edge
        for index, row in enumerate(ROWS):
            self.assertAlmostEqual(
                ROW_WIDTH, sum(width for _, _, width in row), msg=f"row {index}"
            )

    def test_no_key_is_drawn_twice(self):
        seen = [cap.key for row in self.rows for cap in row if cap.key is not None]
        self.assertEqual(len(seen), len(set(seen)))

    def test_function_navigation_and_numpad_keys_are_absent(self):
        caps = {cap.key for row in self.rows for cap in row}
        for name in EXCLUDED:
            key = Keys.from_string(name)
            self.assertIsNotNone(key, f"{name} is not a key name any more")
            self.assertNotIn(key, caps, f"{name} should not be drawn")

    def test_bindings_come_from_the_live_config(self):
        # j is "down" in Normal mode and "enter" with Caps held
        self.assertEqual("down", self.caps("common")[Keys.J].text)
        self.assertEqual("enter", self.caps("special")[Keys.J].text)
        # k has a Normal binding but no special one
        self.assertEqual("up", self.caps("common")[Keys.K].text)
        self.assertEqual("", self.caps("special")[Keys.K].text)

    def test_an_override_shows_up_without_touching_the_layout(self):
        self.config.common[Keys.SEMICOLON] = string_to_multi_keys("ctrl+alt+p")
        self.assertEqual("C-A-p", self.caps("common")[Keys.SEMICOLON].text)

    def test_special_key_and_structural_keys_are_marked(self):
        caps = self.caps()
        self.assertEqual("special_key", caps[self.config.special_key].role)
        self.assertEqual("structural", caps[Keys.SPACE].role)
        self.assertEqual("", caps[Keys.J].role)

    def test_an_unknown_tab_is_refused(self):
        with self.assertRaises(ValueError):
            build(self.config, "nope")

    def test_unnamed_cap_still_draws(self):
        # the right Windows key is on the board but has no name in the Keys map
        unnamed = [cap for row in self.rows for cap in row if cap.key is None]
        self.assertEqual(1, len(unnamed))
        self.assertEqual("structural", unnamed[0].role)
        self.assertFalse(unnamed[0].is_bound)


class TestTabs(unittest.TestCase):
    def setUp(self):
        self.config = Config.from_file(CONFIG_PATH)

    def caps(self, tab):
        return {cap.key: cap for row in build(self.config, tab) for cap in row}

    def test_control_keys_appear_on_the_special_tab(self):
        caps = self.caps("special")
        self.assertEqual("mode", caps[self.config.change_mode_key].text)
        self.assertEqual("control", caps[self.config.change_mode_key].role)
        self.assertEqual("mouse", caps[self.config.mouse_mode_key].text)
        self.assertEqual("off", caps[self.config.off_mode_key].text)
        self.assertEqual("help", caps[self.config.help_key].text)
        self.assertEqual("diag", caps[self.config.diagnostic_key].text)
        self.assertEqual("keys", caps[self.config.keyboard_key].text)

    def test_a_control_key_wins_over_a_special_section_entry(self):
        # process() reaches the control keys first, so the picture must agree
        self.config.special[self.config.change_mode_key] = string_to_multi_keys("f5")
        self.assertEqual("mode", self.caps("special")[self.config.change_mode_key].text)

    def test_control_keys_are_absent_from_the_common_tab(self):
        # caps+f changes mode, but plain f is a first step
        cap = self.caps("common")[self.config.change_mode_key]
        self.assertEqual("prefix", cap.role)

    def test_first_steps_are_counted_on_the_common_tab(self):
        caps = self.caps("common")
        cap = caps[Keys.Q]
        self.assertEqual("prefix", cap.role)
        self.assertTrue(cap.text.startswith("▸"))
        self.assertEqual("keys", cap.detail)

    def test_a_write_or_command_first_step_says_so(self):
        # "a" holds text expansions, not key sends, and must not read as "keys"
        cap = self.caps("common")[Keys.A]
        self.assertEqual("prefix", cap.role)
        self.assertIn("text", cap.detail)

    def test_three_kinds_collapse_so_the_detail_still_fits_a_cap(self):
        from app.events import CMDEvent, WriteEvent

        section = self.config.two_step_events[Keys.Q]
        section[Keys.A] = CMDEvent("anything")
        section[Keys.B] = WriteEvent("anything")
        self.assertEqual("mixed", self.caps("common")[Keys.Q].detail)

    def test_a_first_step_with_nothing_behind_it_is_visible(self):
        cap = self.caps("common")[Keys.S]
        self.assertEqual("prefix", cap.role)
        self.assertEqual("empty", cap.detail)

    def test_first_steps_do_not_appear_on_the_special_tab(self):
        self.assertNotEqual("prefix", self.caps("special")[Keys.Q].role)

    def test_escape_is_reported_as_unplaced_because_it_has_no_cap(self):
        notes = unplaced_controls(self.config)
        self.assertIn(("esc", "exit", "DoKey"), notes)


class TestDescribe(unittest.TestCase):
    def check(self, config_value, expected):
        self.assertEqual(expected, describe(string_to_multi_keys(config_value)))

    def test_empty_binding_is_blank(self):
        self.assertEqual("", describe(None))
        self.assertEqual("", describe([]))

    def test_plain_key_is_itself(self):
        self.check("down", "down")
        self.check("enter", "enter")

    def test_modifiers_collapse_so_a_chord_fits_on_a_cap(self):
        self.check("ctrl+c", "C-c")
        self.check("ctrl+shift+tab", "C-S-tab")
        self.check("shift+f10", "S-f10")

    def test_long_key_names_use_short_forms(self):
        self.check("backspace", "bksp")
        self.check("page down", "pgdn")
        self.check("ctrl+backspace", "C-bksp")

    def test_a_sequence_keeps_its_chords_apart(self):
        self.check("up, end, enter", "up end enter")
        self.check("ctrl+f7,ctrl+f8", "C-f7 C-f8")


if __name__ == "__main__":
    unittest.main()
