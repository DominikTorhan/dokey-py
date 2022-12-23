from typing import List

from app.keys import Keys


class Event:
    """Event types: SendEvent, WriteEvent, MouseEvent, DoKeyEvent (e.g. exit), CMDEvent"""

    def __init__(self, prevent_key_process: bool = False, mouse=False):
        self.prevent_key_process: bool = prevent_key_process # suppress os keyboard event
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
    def __init__(self):
        # now only one case: Exit
        pass

class WriteEvent:
    def __init__(self, text: str):
        self.text = text