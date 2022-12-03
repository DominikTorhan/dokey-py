from app.app import App, KeyboardInterface, TrayAppInterface
from os_keyboard import read_event, keyboard_send
import pystray
from PIL import Image
from pathlib import Path

root = Path(__file__).parent
TRAY_ICON_OFF = str(root / "assets" / "off.ico")
TRAY_ICON_NORMAL = str(root / "assets" / "normal.ico")
TRAY_ICON_INSERT = str(root / "assets" / "insert.ico")
# TrayApp
def start_tray_app():
    def get_icon(state):
        path = TRAY_ICON_OFF
        if state == 1:
            path = TRAY_ICON_NORMAL
        if state == 2:
            path = TRAY_ICON_INSERT
        return Image.open(path)

    def set_icon(state):
        icon.icon = get_icon(state)

    icon = pystray.Icon("Dokey-py", icon=get_icon(0))
    icon.run_detached()

    return set_icon, icon.stop


# main entrypoint
if __name__ == "__main__":
    config_path = str(root / "app" / "config.yaml")
    set_icon, stop_app = start_tray_app()
    keyboard_interface = KeyboardInterface(
        wait_for_keyboard=read_event, send_keyboard_event=keyboard_send
    )
    tray_app_interface = TrayAppInterface(set_icon=set_icon, stop=stop_app)
    app = App(
        config_path=config_path,
        keyboard_interface=keyboard_interface,
        tray_app_interface=tray_app_interface,
    )
    try:
        app.main()
    except:
        stop_app()
