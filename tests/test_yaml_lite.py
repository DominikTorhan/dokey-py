import unittest
from pathlib import Path

from app import yaml_lite

try:
    import yaml  # only present while PyYAML is still installed
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).parent.parent

# Shapes that do not appear in the repo's own YAML but do appear in the user's
# ~/.dokey files, plus the parsing corners that are easy to get wrong.
CASES = {
    "help.yaml shape": (
        "chrome:\n  - ctrl+t  new tab\n  - ctrl+w  close\ncode:\n  - f5 run\n",
        {"chrome": ["ctrl+t  new tab", "ctrl+w  close"], "code": ["f5 run"]},
    ),
    "user_config shape": (
        "d:\n  z: ctrl+f7, ctrl+f8\n  x: __write__<hello>\n",
        {"d": {"z": "ctrl+f7, ctrl+f8", "x": "__write__<hello>"}},
    ),
    "windows path value": (
        "q:\n  d1: __command__<C:\\Program Files\\x\\y.exe> # launch\n",
        {"q": {"d1": "__command__<C:\\Program Files\\x\\y.exe>"}},
    ),
    "value ends with a quote": (
        "q:\n  apostrophe: alt+shift+'\n",
        {"q": {"apostrophe": "alt+shift+'"}},
    ),
    "value ends with a quote, then a comment": (
        "q:\n  apostrophe: alt+shift+' # tricky\n",
        {"q": {"apostrophe": "alt+shift+'"}},
    ),
    "quoted punctuation keys": (
        "';': [99,50]\n',': [73,85]\n",
        {";": [99, 50], ",": [73, 85]},
    ),
    "ints and negatives": ("a: [1, -2, 30]\n", {"a": [1, -2, 30]}),
    "flow mapping with commas inside quotes": (
        'playlist:\n  - {input: "1,,s s down", output: "1||s|||PREV|clear_screen"}\n',
        {"playlist": [{"input": "1,,s s down", "output": "1||s|||PREV|clear_screen"}]},
    ),
    "colon inside a value": ("a: foo:bar\n", {"a": "foo:bar"}),
    "hash that is not a comment": ("a: red#notcomment\n", {"a": "red#notcomment"}),
    "empty value": ("a:\nb: x\n", {"a": None, "b": "x"}),
    "empty document": ("", None),
    "comments only": ("# just a comment\n\n# another\n", None),
}


class TestYamlLite(unittest.TestCase):
    def test_cases(self):
        for name, (text, expected) in CASES.items():
            with self.subTest(name):
                self.assertEqual(expected, yaml_lite.safe_load(text))

    def test_unsupported_shape_raises(self):
        # a block mapping opened on a '-' line must fail loudly, not silently
        # produce the wrong structure
        with self.assertRaises(ValueError):
            yaml_lite.safe_load("items:\n  - key: value\n    other: value\n")

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_matches_pyyaml_on_every_repo_yaml(self):
        paths = sorted(REPO_ROOT.rglob("*.yaml"))
        self.assertTrue(paths, "no YAML files found to compare")
        for path in paths:
            with self.subTest(path.relative_to(REPO_ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(yaml.safe_load(text), yaml_lite.safe_load(text))

    @unittest.skipIf(yaml is None, "PyYAML not installed")
    def test_matches_pyyaml_on_cases(self):
        for name, (text, _) in CASES.items():
            with self.subTest(name):
                self.assertEqual(yaml.safe_load(text), yaml_lite.safe_load(text))
