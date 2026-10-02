import logging
import unittest

from app import yaml_lite
from app.config import Config
from app.keys import VALUE_MARKERS, string_to_multi_keys

# Stands in for a passphrase, a private URL or an address - the things that
# actually live in a __write__ or __command__ binding.
CANARY = "CANARY-secret-do-not-log"

# One document per raise site in yaml_lite, each carrying the canary on the
# line that fails. If a new raise site starts quoting content, this list is the
# place it gets noticed.
BAD_DOCUMENTS = [
    ("unsupported syntax", f"a: &{CANARY}\n"),
    ("unterminated flow sequence", f"a: [{CANARY}\n"),
    ("unterminated flow mapping", "a: {" + CANARY + "\n"),
    ("bad flow mapping entry", "a: {" + CANARY + "}\n"),
    ("unexpected indent", f"a:\n  b: 1\n   c: {CANARY}\n"),
    ("not a mapping entry", f"{CANARY}\n"),
    ("block mapping on a dash", f"a:\n  - k: {CANARY}\n"),
]


class TestParseErrorsDoNotQuoteContent(unittest.TestCase):
    """A parse error travels wherever the caller logs it.

    Config files hold addresses, logins and private URLs, so an error may name
    a location but never repeat what is at it.
    """

    def test_every_failure_names_a_line_and_not_its_contents(self):
        for label, document in BAD_DOCUMENTS:
            with self.subTest(label):
                with self.assertRaises(ValueError) as caught:
                    yaml_lite.safe_load(document)
                message = str(caught.exception)
                self.assertNotIn(CANARY, message, f"{label} leaked the line")
                self.assertIn("line", message, f"{label} gives no location")

    def test_a_valid_document_still_parses(self):
        # the line numbers are threaded through the parser, so prove it still works
        self.assertEqual(
            {"a": {"b": [1, 2], "c": "x"}},
            yaml_lite.safe_load("a:\n  b: [1, 2]\n  c: x\n"),
        )


class TestValuesAreNotEchoedAsKeyNames(unittest.TestCase):
    """Config *values* reach Keys.from_string, not just key names.

    A __write__ or __command__ entry placed where only key sends are accepted
    gets split and looked up a piece at a time; naming the marker instead of
    echoing it is what keeps the payload out of the log.
    """

    def test_marker_values_are_named_not_quoted(self):
        for marker in VALUE_MARKERS:
            with self.subTest(marker):
                with self.assertLogs("app.keys", level="ERROR") as caught:
                    string_to_multi_keys(f"{marker}<{CANARY}>")
                output = "\n".join(caught.output)
                self.assertNotIn(CANARY, output)
                self.assertIn(marker, output)

    def test_an_ordinary_typo_is_still_reported_by_name(self):
        # the point of the message is to find typos; do not redact it into mush
        with self.assertLogs("app.keys", level="ERROR") as caught:
            string_to_multi_keys("ctrl+shfit")
        self.assertIn("shfit", "\n".join(caught.output))

    def test_a_layer_refuses_marker_values_without_repeating_them(self):
        for marker in VALUE_MARKERS:
            with self.subTest(marker):
                with self.assertRaises(ValueError) as caught:
                    Config.convert_dict({"x": f"{marker}<{CANARY}>"})
                message = str(caught.exception)
                self.assertNotIn(CANARY, message)
                self.assertIn(marker, message)


if __name__ == "__main__":
    unittest.main()
