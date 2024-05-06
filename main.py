import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import argparse

import pystray
from PIL import Image

from app.app import (
    App,
    TrayAppInterface,
    HelpInterface,
    MouseInterface,
    DiagnosticsInterface,
)
from app.app_state import NORMAL, INSERT, MOUSE
from app.keys import Keys
from os_level.diagnostic_window import DiagnosticWindow
from os_level.draw_on_screen import WinImage
from os_level.mouse_window import MouseImage
from os_level.os_pynput import PynpytListener

root = Path(__file__).parent
TRAY_ICON_OFF = str(root / "assets" / "off.ico")
TRAY_ICON_NORMAL = str(root / "assets" / "normal.ico")
TRAY_ICON_NORMAL_FIRST_STEP = str(root / "assets" / "normal_first_step.ico")
TRAY_ICON_INSERT = str(root / "assets" / "insert.ico")
TRAY_ICON_MOUSE = str(root / "assets" / "mouse.ico")

STARTING_MODE = NORMAL


# TrayApp
def start_tray_app():
    def get_icon(mode: int, first_step: Keys = Keys.NONE):
        path = TRAY_ICON_OFF
        if mode == NORMAL:
            if first_step == Keys.NONE:
                path = TRAY_ICON_NORMAL
            else:
                path = TRAY_ICON_NORMAL_FIRST_STEP
        if mode == INSERT:
            path = TRAY_ICON_INSERT
        if mode == MOUSE:
            path = TRAY_ICON_MOUSE
        return Image.open(path)

    def set_icon(mode, first_step):
        icon.icon = get_icon(mode, first_step)

    icon = pystray.Icon("Dokey-py", icon=get_icon(STARTING_MODE))
    icon.run_detached()

    return set_icon, icon.stop


def init_logging():
    logger = logging.getLogger()
    # add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    log_dir_path = root / "logs"
    log_dir_path.mkdir(parents=True, exist_ok=True)
    filepath = log_dir_path / "dokey.log"
    file_handler = TimedRotatingFileHandler(
        filename=filepath, when="D", backupCount=7, delay=True
    )

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.critical("init logging!")


# main entrypoint
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Dokey")
    parser.add_argument(
        "-p", "--plain", action="store_true", default=False, help="no graphics mode"
    )  # no graphics mode
    args = parser.parse_args()
    init_logging()
    config_path = str(root / "app" / "config.yaml")
    mouse_config_path = str(root / "app" / "mouse_config.yaml")
    set_icon, stop_app = start_tray_app()
    listener = PynpytListener()
    tray_app_interface = TrayAppInterface(set_icon=set_icon, stop=stop_app)
    if not args.plain:
        win_image = WinImage()
        mouse_image = MouseImage(mouse_config_path)
        diagnostics_window = DiagnosticWindow(None)
        help = HelpInterface(show=win_image.show, hide=win_image.clear)
        mouse = MouseInterface(
            show=mouse_image.show, hide=mouse_image.clear, clear=mouse_image.clear
        )
        diagnostics = DiagnosticsInterface(
            show=mouse_image.show, hide=mouse_image.clear
        )
    else:
        print("Start in plain mode!")
        help = None
        mouse = None
    app = App(
        config_path=config_path,
        mouse_config_path=mouse_config_path,
        listener=listener,
        tray_app_interface=tray_app_interface,
        help_interface=help,
        mouse_interface=mouse,
    )
    try:
        app.main()
    except:
        stop_app()
