from app.app import App
from os_keyboard import read_event, keyboard_send
# TODO: os tray icon

from pathlib import Path


# main entrypoint
if __name__ == "__main__":
    config_path = str(Path(__file__).parent / "app" / "config.yaml")
    app = App(
        func_read_event=read_event, func_send=keyboard_send, config_path=config_path
    )
    app.main()
