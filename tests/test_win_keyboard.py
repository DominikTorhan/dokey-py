"""Exercise input construction without installing a hook or sending real input."""

import ctypes
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.events import SendEvent
from app.keys import Keys, string_to_multi_keys


class TestWindowsKeyboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "os_level" / "win_keyboard.py"
        spec = importlib.util.spec_from_file_location("tested_win_keyboard", path)
        cls.keyboard = importlib.util.module_from_spec(spec)
        with (
            patch.object(ctypes, "WinDLL", create=True),
            patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
            patch.dict("sys.modules", {"os_level.windows_api": Mock()}),
        ):
            spec.loader.exec_module(cls.keyboard)

    def test_win_chord_is_held_until_target_key_is_released(self):
        keyboard = self.keyboard
        listener = keyboard.WindowsListener()
        with patch.object(keyboard, "_send") as send:
            listener.send_keys(string_to_multi_keys("win+r, ctrl+c"))
        actual = [
            [
                (item.ki.wVk, bool(item.ki.dwFlags & keyboard.KEYEVENTF_KEYUP))
                for item in call.args[0]
            ]
            for call in send.call_args_list
        ]
        self.assertEqual(
            actual,
            [
                [
                    (Keys.LEFT_WIN.value, False),
                    (Keys.R.value, False),
                    (Keys.R.value, True),
                    (Keys.LEFT_WIN.value, True),
                ],
                [
                    (Keys.LEFT_CTRL.value, False),
                    (Keys.C.value, False),
                    (Keys.C.value, True),
                    (Keys.LEFT_CTRL.value, True),
                ],
            ],
        )

    def test_execution_failure_passes_original_key_to_next_hook(self):
        keyboard = self.keyboard
        listener = keyboard.WindowsListener()
        listener.func = Mock(return_value=SendEvent([Keys.R]))
        data = keyboard.KBDLLHOOKSTRUCT(vkCode=Keys.R.value)
        with (
            patch.object(keyboard, "is_capslock_on", return_value=False),
            patch.object(keyboard, "get_modif_state"),
            patch.object(listener, "_perform", side_effect=RuntimeError("failed")),
            patch.object(keyboard.user32, "CallNextHookEx", return_value=42) as next_hook,
            self.assertLogs(keyboard.logger, level="ERROR"),
        ):
            result = listener._on_key(
                keyboard.HC_ACTION, keyboard.WM_KEYDOWN, ctypes.addressof(data)
            )
        self.assertEqual(result, 42)
        next_hook.assert_called_once()
