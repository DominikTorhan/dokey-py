import logging
from logging.handlers import TimedRotatingFileHandler
from app.app import App, TrayAppInterface, HelpInterface
from app.app_state import NORMAL, INSERT
from app.keys import Keys
from os_level.os_pynput import PynpytListener
from os_level.draw_on_screen import WinImage
import pystray
from PIL import Image
from pathlib import Path

root = Path(__file__).parent
TRAY_ICON_OFF = str(root / "assets" / "off.ico")
TRAY_ICON_NORMAL = str(root / "assets" / "normal.ico")
TRAY_ICON_NORMAL_FIRST_STEP = str(root / "assets" / "normal_first_step.ico")
TRAY_ICON_INSERT = str(root / "assets" / "insert.ico")

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
    console_handler.setLevel(logging.DEBUG)
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
    init_logging()
    config_path = str(root / "app" / "config.yaml")
    set_icon, stop_app = start_tray_app()
    listener = PynpytListener()
    tray_app_interface = TrayAppInterface(set_icon=set_icon, stop=stop_app)
    win_image = WinImage()
    help = HelpInterface(show=win_image.show, hide=win_image.clear)
    app = App(
        config_path=config_path,
        listener=listener,
        tray_app_interface=tray_app_interface,
        help_interface=help,
    )
    try:
        app.main()
    except:
        stop_app()
