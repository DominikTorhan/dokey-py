from typing import List, Union

from app.keys import Keys


class Event:
    """Base event for actions that only suppress the original keystroke."""

    def __init__(self, prevent_key_process: bool = False, mouse=False):
        self.prevent_key_process: bool = (
            prevent_key_process  # suppress os keyboard event
        )
        self.mouse = mouse


class SendEvent:
    def __init__(self, send: List[Keys] = None):
        if not send:
            send = []
        self.send: List[Keys] = send


class CMDEvent:
    def __init__(self, cmd: str):
        self.cmd: str = cmd


class FocusWindowEvent(Event):
    def __init__(self, process: str, title_prefix: str):
        super().__init__(prevent_key_process=True)
        self.process = process
        self.title_prefix = title_prefix


class FocusOrLaunchEvent(Event):
    def __init__(self, process: str, app_id: str, cmd: str):
        super().__init__(prevent_key_process=True)
        self.process = process
        self.app_id = app_id
        self.cmd = cmd


class DoKeyEvent:
    def __init__(self, event_type: str):
        # Exit or clear screen
        self.event_type = event_type


class WriteEvent:
    def __init__(self, text: str):
        self.text = text


class MouseEvent:
    def __init__(self, rx: float, ry: float):
        self.rx = rx
        self.ry = ry


EventLike = Union[
    Event,
    SendEvent,
    CMDEvent,
    FocusWindowEvent,
    FocusOrLaunchEvent,
    DoKeyEvent,
    WriteEvent,
    MouseEvent,
]
