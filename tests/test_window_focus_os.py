import ctypes
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class TestWindowFocusOS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "os_level" / "window_focus.py"
        spec = importlib.util.spec_from_file_location("tested_window_focus", path)
        cls.focus = importlib.util.module_from_spec(spec)
        cls.user32 = Mock()
        dwmapi = Mock()
        cls.shell32 = Mock()
        cls.ole32 = Mock()
        windows_api = Mock()
        with (
            patch.object(
                ctypes,
                "WinDLL",
                side_effect=[cls.user32, dwmapi, cls.shell32, cls.ole32],
                create=True,
            ),
            patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
            patch.dict("sys.modules", {"os_level.windows_api": windows_api}),
        ):
            spec.loader.exec_module(cls.focus)

    def test_matches_case_insensitively_restores_and_focuses(self):
        focus = self.focus
        user32 = self.user32

        def enumerate_windows(callback, lparam):
            for hwnd in (101, 202):
                if not callback(hwnd, lparam):
                    return False
            return True

        def set_pid(hwnd, pid_pointer):
            pid_pointer._obj.value = hwnd
            return 1

        user32.reset_mock()
        user32.EnumWindows.side_effect = enumerate_windows
        user32.GetWindowThreadProcessId.side_effect = set_pid
        user32.IsIconic.return_value = True
        user32.SetForegroundWindow.return_value = True

        with (
            patch.object(focus, "_is_alt_tab_window", return_value=True),
            patch.object(
                focus,
                "_window_text",
                side_effect=lambda hwnd: {101: "A | shell", 202: "T | editor"}[hwnd],
            ),
            patch.object(
                focus,
                "get_process_name",
                side_effect=lambda pid: {
                    101: "other.exe",
                    202: "wezterm-gui.exe",
                }[pid],
            ),
        ):
            success = focus.focus_window("WEZTERM-GUI.EXE", "t |")

        self.assertTrue(success)
        user32.ShowWindow.assert_called_once_with(202, focus.SW_RESTORE)
        user32.SetForegroundWindow.assert_called_once_with(202)

    def test_process_is_only_looked_up_for_matching_titles(self):
        focus = self.focus
        user32 = self.user32

        def enumerate_windows(callback, lparam):
            for hwnd in (101, 202):
                if not callback(hwnd, lparam):
                    return False
            return True

        user32.reset_mock()
        user32.EnumWindows.side_effect = enumerate_windows
        user32.GetWindowThreadProcessId.side_effect = None
        with (
            patch.object(focus, "_is_alt_tab_window", return_value=True),
            patch.object(
                focus,
                "_window_text",
                side_effect=lambda hwnd: {101: "Elevated", 202: "Other"}[hwnd],
            ),
            patch.object(focus, "get_process_name") as get_process_name,
            self.assertLogs(focus.logger, "WARNING"),
        ):
            success = focus.focus_window("wezterm-gui.exe", "A |")

        self.assertFalse(success)
        get_process_name.assert_not_called()
        user32.SetForegroundWindow.assert_not_called()

    def test_focus_or_launch_matches_process_and_app_id_in_z_order(self):
        focus = self.focus
        user32 = self.user32

        def enumerate_windows(callback, lparam):
            for hwnd in (101, 202, 303):
                if not callback(hwnd, lparam):
                    return False
            return True

        def set_pid(hwnd, pid_pointer):
            pid_pointer._obj.value = hwnd
            return 1

        user32.reset_mock()
        user32.EnumWindows.side_effect = enumerate_windows
        user32.GetWindowThreadProcessId.side_effect = set_pid
        user32.IsIconic.return_value = False
        user32.SetForegroundWindow.return_value = True
        with (
            patch.object(focus, "_window_text", return_value="Chrome"),
            patch.object(focus, "_is_alt_tab_window", return_value=True),
            patch.object(
                focus,
                "get_process_name",
                side_effect=lambda pid: {
                    101: "other.exe",
                    202: "chrome.exe",
                    303: "chrome.exe",
                }[pid],
            ),
            patch.object(
                focus,
                "_window_app_id",
                side_effect=lambda hwnd: {
                    202: "Chrome.UserData.Profile4",
                    303: "Chrome.UserData.Profile2",
                }[hwnd],
            ),
            patch.object(focus.subprocess, "Popen") as popen,
        ):
            result = focus.focus_or_launch(
                "CHROME.EXE", "chrome.userdata.profile2", "start chrome"
            )

        self.assertEqual("focused", result)
        user32.SetForegroundWindow.assert_called_once_with(303)
        popen.assert_not_called()

    def test_focus_or_launch_launches_only_when_no_window_matches(self):
        focus = self.focus
        user32 = self.user32
        user32.reset_mock()
        user32.EnumWindows.side_effect = lambda callback, lparam: callback(
            101, lparam
        )
        user32.GetWindowThreadProcessId.side_effect = (
            lambda hwnd, pointer: setattr(pointer._obj, "value", hwnd) or 1
        )
        with (
            patch.object(focus, "_window_text", return_value="Chrome"),
            patch.object(focus, "_is_alt_tab_window", return_value=True),
            patch.object(focus, "get_process_name", return_value="chrome.exe"),
            patch.object(
                focus, "_window_app_id", return_value="Chrome.UserData.Profile4"
            ),
            patch.object(focus.subprocess, "Popen") as popen,
        ):
            result = focus.focus_or_launch(
                "chrome.exe", "Chrome.UserData.Profile2", "start chrome profile-2"
            )

        self.assertEqual("launched", result)
        user32.SetForegroundWindow.assert_not_called()
        popen.assert_called_once_with(
            "start chrome profile-2",
            shell=True,
            stdin=focus.subprocess.DEVNULL,
            stdout=focus.subprocess.DEVNULL,
            stderr=focus.subprocess.DEVNULL,
            creationflags=getattr(focus.subprocess, "CREATE_NO_WINDOW", 0),
        )


if __name__ == "__main__":
    unittest.main()
