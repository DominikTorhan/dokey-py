import logging
from logging.handlers import TimedRotatingFileHandler
from app.app import App, TrayAppInterface, ListenerABC
from app.current_state import NORMAL, OFF, INSERT
from os_pynput import PynpytListener
import pystray
from PIL import Image
from pathlib import Path

root = Path(__file__).parent
TRAY_ICON_OFF = str(root / "assets" / "off.ico")
TRAY_ICON_NORMAL = str(root / "assets" / "normal.ico")
TRAY_ICON_INSERT = str(root / "assets" / "insert.ico")

STARTING_MODE = NORMAL
# TrayApp
def start_tray_app():
    def get_icon(mode):
        path = TRAY_ICON_OFF
        if mode == NORMAL:
            path = TRAY_ICON_NORMAL
        if mode == INSERT:
            path = TRAY_ICON_INSERT
        return Image.open(path)

    def set_icon(mode):
        icon.icon = get_icon(mode)

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
    #file_handler = logging.FileHandler(filepath, mode="w")
    file_handler = TimedRotatingFileHandler(
        filename=filepath, when="D", backupCount=7, delay=True
    )

    #formatter = logging.Formatter(DEFAULT_FORMAT)
    #file_handler.setFormatter(formatter)

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
    app = App(
        config_path=config_path,
        listener=listener,
        tray_app_interface=tray_app_interface,
    )
    try:
        app.main()
    except:
        stop_app()
