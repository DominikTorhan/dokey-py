from typing import List, Union

from app.keys import Keys


class Event:
    """Event types: SendEvent, WriteEvent, MouseEvent, DoKeyEvent (e.g. exit), CMDEvent"""

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


EventLike = Union[Event, SendEvent, CMDEvent, DoKeyEvent, WriteEvent, MouseEvent]
