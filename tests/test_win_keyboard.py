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
            patch.object(ctypes, "WinDLL", create=True) as win_dll,
            patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
            patch.dict("sys.modules", {"os_level.windows_api": Mock()}),
        ):
            # stands in for the layout table: any non-zero code will do, it
            # only has to be a real int so it can go into a WORD field
            win_dll.return_value.MapVirtualKeyW.side_effect = cls.scan_code
            spec.loader.exec_module(cls.keyboard)

    @staticmethod
    def scan_code(vk, _mapping):
        return 0x80 | (vk & 0x7F)

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

    def test_repeats_ignore_injected_events_and_reset_after_key_up(self):
        keyboard = self.keyboard
        listener = keyboard.WindowsListener()
        listener.func = Mock(return_value=SendEvent([Keys.DOWN]))
        physical = keyboard.KBDLLHOOKSTRUCT(vkCode=Keys.J.value)
        injected = keyboard.KBDLLHOOKSTRUCT(
            vkCode=Keys.J.value, dwExtraInfo=keyboard.DOKEY_EXTRA_INFO
        )
        with (
            patch.object(keyboard, "is_capslock_on", return_value=False),
            patch.object(keyboard, "get_modif_state"),
            patch.object(listener, "_perform", return_value=True),
        ):
            for message, data in (
                (keyboard.WM_KEYDOWN, physical),
                (keyboard.WM_KEYUP, injected),
                (keyboard.WM_KEYDOWN, physical),
                (keyboard.WM_KEYUP, physical),
                (keyboard.WM_KEYDOWN, physical),
            ):
                listener._on_key(keyboard.HC_ACTION, message, ctypes.addressof(data))
        self.assertEqual(
            [False, True, False, False],
            [call.args[0].is_repeat for call in listener.func.call_args_list],
        )

    def test_unsupported_key_is_counted_but_diagnosed_only_once(self):
        keyboard = self.keyboard
        listener = keyboard.WindowsListener()
        data = keyboard.KBDLLHOOKSTRUCT(vkCode=175)
        with (
            patch.object(keyboard, "is_capslock_on", return_value=False),
            patch.object(keyboard.usage, "record") as usage_record,
            self.assertLogs(keyboard.logger, level="INFO") as logs,
        ):
            for message in (keyboard.WM_KEYDOWN, keyboard.WM_KEYDOWN,
                            keyboard.WM_KEYUP, keyboard.WM_KEYDOWN):
                listener._on_key(keyboard.HC_ACTION, message, ctypes.addressof(data))
        self.assertEqual(1, len(logs.output))
        self.assertEqual(3, usage_record.call_count)
        self.assertEqual(
            [False, True, False],
            [call.kwargs["repeat"] for call in usage_record.call_args_list],
        )

    def test_text_injection_does_not_log_its_contents(self):
        with (
            patch.object(self.keyboard, "_send"),
            patch.object(self.keyboard.logger, "info") as info,
        ):
            self.keyboard.WindowsListener().write_text("private text")
        info.assert_not_called()

    def test_injected_keys_carry_a_scan_code(self):
        """A wVk-only event reaches the foreground window with scanCode 0.

        Windows itself does not mind, but a window that reads the scan code
        instead of the virtual key - cmder is one - then decodes a key that
        does not exist and shows a stray character next to the real one.
        """
        keyboard = self.keyboard
        listener = keyboard.WindowsListener()
        with patch.object(keyboard, "_send") as send:
            listener.send_keys(string_to_multi_keys("ctrl+v"))
        items = send.call_args.args[0]
        self.assertEqual(
            [
                (Keys.LEFT_CTRL.value, self.scan_code(Keys.LEFT_CTRL.value, 0)),
                (Keys.V.value, self.scan_code(Keys.V.value, 0)),
                (Keys.V.value, self.scan_code(Keys.V.value, 0)),
                (Keys.LEFT_CTRL.value, self.scan_code(Keys.LEFT_CTRL.value, 0)),
            ],
            [(item.ki.wVk, item.ki.wScan) for item in items],
        )

    def test_extended_keys_keep_the_unextended_scan_code(self):
        """The extended flag and the 0xE0 prefix are the same statement.

        MapVirtualKey returns the unextended code and KEYEVENTF_EXTENDEDKEY
        supplies the prefix; sending a pre-extended code alongside the flag
        would say it twice and land on the numpad twin.
        """
        keyboard = self.keyboard
        with patch.object(keyboard, "_send") as send:
            keyboard.WindowsListener().send_keys([Keys.LEFT])
        item = send.call_args.args[0][0]
        self.assertTrue(item.ki.dwFlags & keyboard.KEYEVENTF_EXTENDEDKEY)
        self.assertEqual(self.scan_code(Keys.LEFT.value, 0), item.ki.wScan)
