from app.app import App, TrayAppInterface, ListenerABC
from app.app_state import NORMAL, OFF, INSERT
from os_pynput import PynpytListener
import pystray
from PIL import Image
from pathlib import Path

root = Path(__file__).parent
TRAY_ICON_OFF = str(root / "assets" / "off.ico")
TRAY_ICON_NORMAL = str(root / "assets" / "normal.ico")
TRAY_ICON_INSERT = str(root / "assets" / "insert.ico")

STARTING_STATE = NORMAL
# TrayApp
def start_tray_app():
    def get_icon(state):
        path = TRAY_ICON_OFF
        if state == NORMAL:
            path = TRAY_ICON_NORMAL
        if state == INSERT:
            path = TRAY_ICON_INSERT
        return Image.open(path)

    def set_icon(state):
        icon.icon = get_icon(state)

    icon = pystray.Icon("Dokey-py", icon=get_icon(STARTING_STATE))
    icon.run_detached()

    return set_icon, icon.stop


# main entrypoint
if __name__ == "__main__":
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
